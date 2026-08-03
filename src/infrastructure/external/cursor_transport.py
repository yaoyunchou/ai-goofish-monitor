"""
Cursor SDK transport for AI completions.
"""
from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, Optional, Tuple, Union

from cursor_sdk import (
    AgentOptions,
    AsyncAgent,
    AsyncClient,
    CloudAgentOptions,
    CloudRepository,
    LocalAgentOptions,
    SDKImage,
    UserMessage,
)

from src.infrastructure.config.settings import AISettings


class CursorAITransport:
    """Use Cursor SDK one-shot prompts for text / vision analysis."""

    def __init__(self, settings: AISettings):
        self.settings = settings

    def is_available(self) -> bool:
        return self.settings.is_cursor_configured()

    async def close(self) -> None:
        return None

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        *,
        enable_json_output: bool = True,
    ) -> str:
        text, images = _extract_message_parts(messages)
        if enable_json_output and "json" not in text.lower():
            text += (
                "\n\n请只返回合法的 JSON 对象，不要包含 markdown 代码块或额外说明。"
            )

        user_message: Union[str, UserMessage] = text
        if images:
            user_message = UserMessage(text=text, images=images)

        workspace = self._resolve_local_cwd()
        self._apply_api_key_env()
        async with await AsyncClient.launch_bridge(
            workspace=workspace,
            allow_api_key_env_fallback=True,
        ) as client:
            result = await AsyncAgent.prompt(
                user_message,
                self._build_agent_options(),
                client=client,
            )
        status = getattr(result, "status", None)
        if status in {"error", "cancelled", "expired"}:
            raise RuntimeError(
                f"Cursor agent run failed with status={status}: {result.result or 'unknown error'}"
            )
        response_text = (result.result or "").strip()
        if not response_text:
            raise RuntimeError("Cursor agent returned an empty response")
        return response_text

    def _build_agent_options(self) -> AgentOptions:
        runtime = self.settings.effective_cursor_runtime()
        options_kwargs: Dict[str, Any] = {
            "model": self.settings.cursor_model_name,
            "api_key": self.settings.cursor_api_key,
        }
        if runtime == "cloud":
            options_kwargs["cloud"] = self._build_cloud_options()
        else:
            options_kwargs["local"] = LocalAgentOptions(
                cwd=self._resolve_local_cwd(),
            )
        return AgentOptions(**options_kwargs)

    def _build_cloud_options(self) -> CloudAgentOptions:
        repos = self._parse_cloud_repos(self.settings.cursor_cloud_repos)
        if not repos:
            repos = self._parse_cloud_repos(_detect_git_remote_repo_url())
        if repos:
            return CloudAgentOptions(repos=repos)
        return CloudAgentOptions()

    def _resolve_local_cwd(self) -> str:
        configured = (self.settings.cursor_local_cwd or ".").strip()
        path = os.path.abspath(configured)
        os.makedirs(path, exist_ok=True)
        return path

    def _apply_api_key_env(self) -> None:
        api_key = (self.settings.cursor_api_key or "").strip()
        if api_key:
            os.environ["CURSOR_API_KEY"] = api_key

    @staticmethod
    def _parse_cloud_repos(raw_value: Optional[str]) -> List[CloudRepository]:
        if not raw_value:
            return []
        repos: List[CloudRepository] = []
        for entry in str(raw_value).split(","):
            url = entry.strip()
            if url:
                repos.append(CloudRepository(url=url))
        return repos


def _extract_message_parts(
    messages: List[Dict[str, Any]],
) -> Tuple[str, List[SDKImage]]:
    text_parts: List[str] = []
    images: List[SDKImage] = []

    for message in messages:
        role = str(message.get("role") or "user")
        if role != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            text_parts.append(content)
            continue
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "text":
                text_parts.append(str(item.get("text") or ""))
            elif item_type == "image_url":
                image_url = _extract_image_url(item)
                sdk_image = _image_url_to_sdk_image(image_url)
                if sdk_image is not None:
                    images.append(sdk_image)

    text = "\n".join(part for part in text_parts if part).strip()
    if not text:
        raise ValueError("Cursor transport requires non-empty user text content")
    return text, images


def _extract_image_url(item: Dict[str, Any]) -> str:
    image_url = item.get("image_url")
    if isinstance(image_url, dict):
        return str(image_url.get("url") or "")
    return str(image_url or "")


def _image_url_to_sdk_image(image_url: str) -> Optional[SDKImage]:
    if not image_url:
        return None
    if image_url.startswith("data:"):
        return _data_url_to_sdk_image(image_url)
    if image_url.startswith("http://") or image_url.startswith("https://"):
        return SDKImage.url_image(image_url)
    if os.path.exists(image_url):
        return SDKImage.from_file(image_url)
    return None


def _data_url_to_sdk_image(data_url: str) -> SDKImage:
    header, _, encoded = data_url.partition(",")
    mime_type = "image/jpeg"
    if header.startswith("data:"):
        mime_type = header[5:].split(";", 1)[0] or mime_type
    return SDKImage.data_image(encoded, mime_type)


def _detect_git_remote_repo_url() -> str:
    """Best-effort origin URL for Cursor CloudAgentOptions (github.com/org/repo)."""
    try:
        raw = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=os.getcwd(),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""
    return _normalize_repo_url_for_cursor(raw)


def _normalize_repo_url_for_cursor(remote_url: str) -> str:
    url = (remote_url or "").strip()
    if not url:
        return ""
    if url.startswith("git@"):
        host_path = url[4:]
        host, _, path = host_path.partition(":")
        path = path.removesuffix(".git")
        return f"{host}/{path}" if host and path else ""
    url = url.removesuffix(".git")
    for prefix in ("https://", "http://"):
        if url.startswith(prefix):
            return url[len(prefix) :]
    return url

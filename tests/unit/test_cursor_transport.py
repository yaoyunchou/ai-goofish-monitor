import asyncio
from types import SimpleNamespace

import pytest

from src.infrastructure.config.settings import AISettings
from src.infrastructure.external.cursor_transport import (
    CursorAITransport,
    _extract_message_parts,
)


def test_extract_message_parts_supports_text_and_data_url_images():
    text, images = _extract_message_parts(
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64,ZmFrZQ=="},
                    },
                    {"type": "text", "text": "分析这件商品"},
                ],
            }
        ]
    )

    assert "分析这件商品" in text
    assert len(images) == 1


def test_cursor_transport_complete_uses_async_agent_prompt(monkeypatch):
    settings = AISettings(
        provider="cursor",
        cursor_api_key="test-key",
        cursor_model_name="composer-2.5",
        cursor_runtime="local",
        cursor_local_cwd=".",
    )
    transport = CursorAITransport(settings)

    captured = {}

    class FakeResult:
        status = "finished"
        result = '{"is_recommended": true, "reason": "ok"}'

    async def fake_prompt(message, options, **kwargs):
        captured["message"] = message
        captured["options"] = options
        return FakeResult()

    monkeypatch.setattr(
        "src.infrastructure.external.cursor_transport.AsyncAgent.prompt",
        fake_prompt,
    )

    class _FakeClient:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *args):
            return None

    async def fake_launch_bridge(*args, **kwargs):
        return _FakeClient()

    monkeypatch.setattr(
        "src.infrastructure.external.cursor_transport.AsyncClient.launch_bridge",
        fake_launch_bridge,
    )

    response = asyncio.run(
        transport.complete(
            [{"role": "user", "content": "请返回 JSON"}],
            enable_json_output=True,
        )
    )

    assert '{"is_recommended": true, "reason": "ok"}' in response
    assert captured["options"].model == "composer-2.5"


def test_ai_settings_cursor_provider_configuration():
    settings = AISettings(
        AI_PROVIDER="cursor",
        CURSOR_API_KEY="key",
        CURSOR_MODEL_NAME="composer-2.5",
    )
    assert settings.normalized_provider() == "cursor"
    assert settings.is_configured() is True
    assert settings.active_model_name() == "composer-2.5"


def test_effective_cursor_runtime_auto_cloud_in_cursor_agent(monkeypatch):
    monkeypatch.delenv("CURSOR_RUNTIME", raising=False)
    monkeypatch.setenv("CURSOR_AGENT", "1")
    settings = AISettings(cursor_runtime="")
    assert settings.effective_cursor_runtime() == "cloud"


def test_effective_cursor_runtime_respects_explicit_local(monkeypatch):
    monkeypatch.setenv("CURSOR_AGENT", "1")
    settings = AISettings(cursor_runtime="local")
    assert settings.effective_cursor_runtime() == "local"


def test_normalize_repo_url_for_cursor():
    from src.infrastructure.external.cursor_transport import _normalize_repo_url_for_cursor

    assert (
        _normalize_repo_url_for_cursor("git@github.com:yaoyunchou/ai-goofish-monitor.git")
        == "github.com/yaoyunchou/ai-goofish-monitor"
    )
    assert (
        _normalize_repo_url_for_cursor("https://github.com/org/repo.git")
        == "github.com/org/repo"
    )


def test_ai_client_uses_cursor_transport_when_provider_is_cursor(monkeypatch):
    from src.infrastructure.external.ai_client import AIClient

    client = AIClient.__new__(AIClient)
    client.settings = AISettings(
        AI_PROVIDER="cursor",
        CURSOR_API_KEY="key",
        CURSOR_MODEL_NAME="composer-2.5",
    )
    client.client = None
    client.cursor_transport = CursorAITransport(client.settings)

    async def fake_complete(messages, *, enable_json_output=True):
        assert enable_json_output is True
        return '{"ok": true}'

    monkeypatch.setattr(client.cursor_transport, "complete", fake_complete)

    response = asyncio.run(
        client._call_ai([{"role": "user", "content": "hello"}])
    )
    assert response == '{"ok": true}'

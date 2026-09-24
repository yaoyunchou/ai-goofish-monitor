"""笔记链接与互动数字。浏览数页面没有就保持空。"""
from __future__ import annotations

import re
from dataclasses import dataclass

_NOTE_ID = re.compile(r"(?:discovery/item|explore)/([0-9a-fA-F]{16,})", re.IGNORECASE)
_LOGIN_MARKERS = ("登录后", "请登录", "扫码登录", "login-container")
_FIELDS = (
    ("liked_count", r"(?:likedCount|liked_count|likes)", r"(?:点赞|赞)"),
    ("collected_count", r"(?:collectedCount|collected_count|collects)", r"收藏"),
    ("comment_count", r"(?:commentCount|comment_count|comments)", r"评论"),
    ("view_count", r"(?:viewCount|view_count|views)", r"浏览"),
)
_TITLE = re.compile(r'"(?:title|noteTitle)"\s*:\s*"([^"\\]{1,200})"')
_AUTHOR = re.compile(r'"(?:nickname|authorName)"\s*:\s*"([^"\\]{1,80})"')
_COVER = re.compile(r'"(?:cover|image)"\s*:\s*"(https:[^"]+)"')


@dataclass(frozen=True)
class NoteFields:
    liked_count: int | None
    collected_count: int | None
    comment_count: int | None
    view_count: int | None
    title: str | None
    author_name: str | None
    cover_url: str | None
    login_required: bool


def parse_note_id(text: str) -> str | None:
    match = _NOTE_ID.search(text or "")
    if match:
        return match.group(1).lower()
    return None


def parse_note_html(html: str, status_code: int = 200) -> NoteFields:
    body = html or ""
    login = status_code in (401, 461) or any(marker in body for marker in _LOGIN_MARKERS)
    counts = {name: _count(body, json_key, label) for name, json_key, label in _FIELDS}
    if login and all(value is None for value in counts.values()):
        return NoteFields(None, None, None, None, None, None, None, True)
    title = _first(_TITLE, body)
    author = _first(_AUTHOR, body)
    cover = _first(_COVER, body)
    return NoteFields(
        counts["liked_count"],
        counts["collected_count"],
        counts["comment_count"],
        counts["view_count"],
        title,
        author,
        cover,
        False,
    )


def _count(body: str, json_key: str, label: str) -> int | None:
    matched = re.search(rf'"{json_key}"\s*:\s*(\d+)', body)
    if matched:
        return int(matched.group(1))
    text = re.search(rf"{label}\s*([0-9]+(?:\.[0-9]+)?)\s*(万)?", body)
    if not text:
        return None
    value = float(text.group(1))
    if text.group(2):
        value *= 10000
    return int(value)


def _first(pattern: re.Pattern[str], body: str) -> str | None:
    matched = pattern.search(body)
    if not matched:
        return None
    return matched.group(1).replace("\\u002F", "/")

"""业务时区（Asia/Shanghai）时间工具。"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def shanghai_now() -> datetime:
    return datetime.now(tz=SHANGHAI_TZ)


def shanghai_now_iso() -> str:
    return shanghai_now().isoformat()


def shanghai_today(now: datetime | None = None) -> date:
    current = now or shanghai_now()
    return current.astimezone(SHANGHAI_TZ).date()


def to_shanghai_iso(value: datetime | str | None) -> str | None:
    """将时间统一序列化为带 +08:00 的 ISO 字符串，供 API / 前端展示。"""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
    elif isinstance(value, datetime):
        dt = value
    else:
        return str(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SHANGHAI_TZ)
    return dt.astimezone(SHANGHAI_TZ).isoformat()

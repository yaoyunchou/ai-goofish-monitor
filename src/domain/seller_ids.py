"""卖家 userId / 店铺链接解析与订阅过滤。"""
from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import parse_qs, urlparse

DEFAULT_SELLER_SUBSCRIPTION_ITEM_LIMIT = 100

_USER_ID_RE = re.compile(r"^\d{5,}$")
_INVALID_METRIC_TOKENS = {None, "", "nan", "NaN", "-", "未知", "n/a", "N/A", "null", "None"}


def parse_seller_user_ids(*values: Iterable | str | None) -> list[str]:
    raw_chunks: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            raw_chunks.extend(re.split(r"[\n,]+", value))
            continue
        if isinstance(value, (list, tuple, set)):
            for item in value:
                raw_chunks.extend(parse_seller_user_ids(item))
            continue
        raw_chunks.append(str(value))

    seen: set[str] = set()
    result: list[str] = []
    for chunk in raw_chunks:
        user_id = extract_seller_user_id(chunk)
        if not user_id or user_id in seen:
            continue
        seen.add(user_id)
        result.append(user_id)
    return result


def extract_seller_user_id(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if _USER_ID_RE.match(text):
        return text
    parsed = urlparse(text)
    query = parse_qs(parsed.query)
    candidates = query.get("userId") or query.get("userid") or []
    for candidate in candidates:
        candidate = str(candidate).strip()
        if _USER_ID_RE.match(candidate):
            return candidate
    match = re.search(r"(?:userId|userid)=(\d{5,})", text)
    if match:
        return match.group(1)
    return None


def build_subscription_keyword(task_name: str) -> str:
    slug = "".join(
        char for char in str(task_name or "").lower().replace(" ", "_")
        if char.isalnum() or char in "_-"
    ).rstrip("_")
    return f"seller_sub_{slug or 'task'}"


def build_shop_datacompass_keyword(task_name: str) -> str:
    slug = "".join(
        char for char in str(task_name or "").lower().replace(" ", "_")
        if char.isalnum() or char in "_-"
    ).rstrip("_")
    return f"shop_datacompass_{slug or 'task'}"


def is_valid_metric_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    text = str(value).strip()
    if text in _INVALID_METRIC_TOKENS or text.lower() in {"nan", "n/a", "null", "none"}:
        return False
    return True


def has_want_and_view(item_data: dict | None) -> bool:
    payload = item_data or {}
    want = payload.get("“想要”人数")
    if want is None:
        want = payload.get("想要人数")
    view = payload.get("浏览量")
    return is_valid_metric_value(want) and is_valid_metric_value(view)


def parse_metric_int(value) -> int | None:
    if not is_valid_metric_value(value):
        return None
    text = str(value).strip().replace(",", "")
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None

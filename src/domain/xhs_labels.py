"""店铺名、分类、标记的长度和去重。"""
from __future__ import annotations

import re

_TAG_SPLIT = re.compile(r"[,，、]")
_MAX_SHOP = 80
_MAX_CATEGORY = 40
_MAX_TAG = 20
_MAX_TAGS = 8


def normalize_shop_name(value: str | None) -> str | None:
    return _clip(value, _MAX_SHOP, "店铺名")


def normalize_category(value: str | None) -> str | None:
    return _clip(value, _MAX_CATEGORY, "分类")


def normalize_tags(values: list[str] | None) -> list[str]:
    if not values:
        return []
    seen: list[str] = []
    for raw in values:
        tag = _clip(raw, _MAX_TAG, "标记")
        if tag and tag not in seen:
            seen.append(tag)
    if len(seen) > _MAX_TAGS:
        raise ValueError(f"标记最多 {_MAX_TAGS} 个")
    return seen


def split_tag_cell(value: str | None) -> list[str] | None:
    text = (value or "").strip()
    if not text:
        return None
    return normalize_tags(_TAG_SPLIT.split(text))


def _clip(value: str | None, limit: int, label: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if len(text) > limit:
        raise ValueError(f"{label}不能超过 {limit} 个字")
    return text

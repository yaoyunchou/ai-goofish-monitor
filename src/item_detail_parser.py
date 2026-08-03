"""
从闲鱼商品详情 API 响应中解析 SKU 与价格。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def _format_price(value: Any) -> tuple[Optional[float], str]:
    if value is None:
        return None, ""
    if isinstance(value, dict):
        for key in ("price", "priceText", "text", "value"):
            if key in value:
                return _format_price(value.get(key))
        return None, ""
    if isinstance(value, (int, float)):
        number = round(float(value), 2)
        if number > 10000:
            number = round(number / 100, 2)
        return number, f"¥{number:g}"
    text = str(value).strip().replace("¥", "").replace(",", "")
    if not text:
        return None, ""
    try:
        number = round(float(text), 2)
        return number, f"¥{number:g}"
    except ValueError:
        return None, str(value)


def _property_label(entry: dict) -> str:
    parts: List[str] = []
    for key in ("propertyText", "name", "propName", "key"):
        name = entry.get(key)
        if name:
            parts.append(str(name).strip())
            break
    for key in ("valueText", "value", "val", "text"):
        val = entry.get(key)
        if val:
            parts.append(str(val).strip())
            break
    if len(parts) == 2:
        return f"{parts[0]}: {parts[1]}"
    if parts:
        return parts[0]
    return ""


def _build_sku_label(properties: List[dict], fallback: str = "") -> str:
    labels = [_property_label(prop) for prop in properties if isinstance(prop, dict)]
    labels = [label for label in labels if label]
    if labels:
        return " / ".join(labels)
    return fallback or "默认规格"


def _normalize_sku_entry(raw: dict, *, fallback_title: str = "") -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    sku_id = (
        raw.get("skuId")
        or raw.get("sku_id")
        or raw.get("id")
        or raw.get("itemSkuId")
    )
    price_raw = (
        raw.get("price")
        or raw.get("skuPrice")
        or raw.get("promotionPrice")
        or raw.get("actPrice")
    )
    price_number, price_display = _format_price(price_raw)
    properties = (
        raw.get("propertyList")
        or raw.get("properties")
        or raw.get("propList")
        or []
    )
    if not isinstance(properties, list):
        properties = []
    label = raw.get("skuText") or raw.get("title") or _build_sku_label(properties, fallback_title)
    if price_number is None and not price_display and not label:
        return None
    return {
        "sku_id": str(sku_id) if sku_id is not None else "",
        "label": str(label).strip() or fallback_title or "默认规格",
        "price": price_number,
        "price_display": price_display or (f"¥{price_number:g}" if price_number is not None else ""),
        "properties": properties,
        "in_stock": raw.get("canBuy", raw.get("inStock", True)),
    }


def _collect_sku_lists(node: Any, bucket: List[dict]) -> None:
    if isinstance(node, dict):
        for key in (
            "skuList",
            "itemSkuList",
            "skuInfoList",
            "skus",
            "skuVOList",
            "idleItemSkuList",
        ):
            value = node.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        bucket.append(item)
        for value in node.values():
            _collect_sku_lists(value, bucket)
    elif isinstance(node, list):
        for item in node:
            _collect_sku_lists(item, bucket)


def _parse_cpv_sku_map(item_do: dict) -> List[Dict[str, Any]]:
    skus: List[Dict[str, Any]] = []
    cpv_list = item_do.get("cpvList") or item_do.get("cpvlist") or []
    price_map = item_do.get("skuPriceMap") or item_do.get("skuPriceVOMap") or {}
    if not isinstance(cpv_list, list) or not isinstance(price_map, dict):
        return skus
    for cpv in cpv_list:
        if not isinstance(cpv, dict):
            continue
        sku_id = cpv.get("skuId") or cpv.get("id")
        price_info = price_map.get(str(sku_id)) if sku_id is not None else None
        merged = dict(cpv)
        if isinstance(price_info, dict):
            merged.update(price_info)
        elif price_info is not None:
            merged["price"] = price_info
        normalized = _normalize_sku_entry(merged)
        if normalized:
            skus.append(normalized)
    return skus


async def extract_skus_from_detail_payloads(
    payloads: List[dict],
    *,
    fallback_title: str = "",
) -> List[Dict[str, Any]]:
    """合并多次详情/sku 接口响应，返回去重后的 SKU 列表。"""
    raw_entries: List[dict] = []
    item_do: dict = {}

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if not isinstance(data, dict):
            continue
        current_item_do = data.get("itemDO") or data.get("itemDo") or {}
        if isinstance(current_item_do, dict) and current_item_do:
            item_do = {**item_do, **current_item_do}
        _collect_sku_lists(data, raw_entries)
        _collect_sku_lists(payload, raw_entries)

    normalized: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for raw in raw_entries:
        entry = _normalize_sku_entry(raw, fallback_title=fallback_title)
        if not entry:
            continue
        dedup = entry["sku_id"] or entry["label"]
        if dedup in seen:
            continue
        seen.add(dedup)
        normalized.append(entry)

    if not normalized and item_do:
        normalized.extend(_parse_cpv_sku_map(item_do))
        if not normalized:
            single = _normalize_sku_entry(
                {
                    "skuId": item_do.get("itemId") or item_do.get("id"),
                    "price": item_do.get("soldPrice") or item_do.get("price"),
                    "propertyList": item_do.get("propertyList") or [],
                    "title": fallback_title or item_do.get("title"),
                },
                fallback_title=fallback_title or str(item_do.get("title") or ""),
            )
            if single:
                normalized.append(single)

    return normalized


def parse_title_sku_fragments(title: str) -> List[Dict[str, str]]:
    """从搜索标题中解析「颜色分类 / 长度」类片段（无多 SKU 价时的补充）。"""
    text = str(title or "")
    if not text:
        return []
    fragments: List[Dict[str, str]] = []
    for segment in text.replace("，", ",").split(","):
        piece = segment.strip()
        if ":" in piece or "：" in piece:
            sep = "：" if "：" in piece else ":"
            name, value = piece.split(sep, 1)
            name = name.strip()
            value = value.strip()
            if name and value:
                fragments.append({"name": name, "value": value})
    return fragments

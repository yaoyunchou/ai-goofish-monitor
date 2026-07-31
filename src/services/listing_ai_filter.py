"""
抓取后统一 AI 品类过滤：在完整 EagleEye 分析之前剔除数据线等非目标商品。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from src.config import ENABLE_RESPONSE_FORMAT, MODEL_NAME
from src.ai_message_builder import build_user_message_content
from src.infrastructure.external.ai_client import AIClient
from src.services.ai_response_parser import parse_ai_response_json

_FILTER_PROMPT_PATH = os.path.join("prompts", "listing_ai_filter_system.txt")
_VALID_CATEGORIES = frozenset(
    {
        "charger_head",
        "data_cable_only",
        "cable_and_charger_bundle",
        "adapter_accessory",
        "unclear",
        "other",
    }
)


def _load_filter_system_template() -> str:
    try:
        with open(_FILTER_PROMPT_PATH, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return (
            "判断商品是否符合购买意图，仅输出 JSON："
            '{"is_target_product":bool,"detected_category":"string","reason":"string"}'
        )


def _build_filter_prompt(purchase_intent: str) -> str:
    template = _load_filter_system_template()
    intent = (purchase_intent or "").strip() or "用户未提供详细意图，请根据商品标题与品类常识判断是否为充电头而非单独数据线。"
    return template.replace("{{PURCHASE_INTENT}}", intent)


def _compact_product_json(record: dict) -> str:
    item = record.get("商品信息", {}) or {}
    payload = {
        "任务名称": record.get("任务名称"),
        "搜索关键字": record.get("搜索关键字"),
        "商品标题": item.get("商品标题"),
        "当前售价": item.get("当前售价"),
        "商品标签": item.get("商品标签"),
        "商品ID": item.get("商品ID"),
    }
    seller = record.get("卖家信息", {}) or {}
    if seller:
        payload["卖家信息摘要"] = {
            key: seller.get(key)
            for key in ("卖家昵称", "卖家芝麻信用", "卖家注册时长")
            if seller.get(key) is not None
        }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _normalize_filter_response(parsed: dict) -> Dict[str, Any]:
    is_target = parsed.get("is_target_product")
    if not isinstance(is_target, bool):
        is_target = bool(is_target)
    category = str(parsed.get("detected_category") or "unclear").strip().lower()
    if category not in _VALID_CATEGORIES:
        category = "other"
    reason = str(parsed.get("reason") or "").strip() or (
        "AI 品类过滤：符合目标商品。" if is_target else "AI 品类过滤：不符合目标商品。"
    )
    return {
        "is_target_product": is_target,
        "detected_category": category,
        "reason": reason,
    }


def build_filter_analysis_result(
    filter_payload: Dict[str, Any],
    *,
    keyword_hit_count: int = 0,
) -> Dict[str, Any]:
    """将过滤结果转为与 ai_analysis 兼容的结构。"""
    is_target = bool(filter_payload.get("is_target_product"))
    reason = str(filter_payload.get("reason") or "")
    category = filter_payload.get("detected_category")
    if not is_target and category == "data_cable_only" and "数据线" not in reason:
        reason = f"仅为数据线/线材，非充电头：{reason}"
    return {
        "analysis_source": "ai_filter",
        "is_recommended": is_target,
        "reason": reason,
        "keyword_hit_count": keyword_hit_count,
        "filter": {
            "detected_category": category,
            "is_target_product": is_target,
        },
    }


async def filter_listing_by_ai(
    record: dict,
    *,
    purchase_intent: str,
    image_paths: Optional[List[str]] = None,
    max_images: int = 2,
    ai_client: Optional[AIClient] = None,
) -> Optional[Dict[str, Any]]:
    """
    调用 AI 做轻量品类判断。失败返回 None（调用方决定是否放行）。
    """
    from src.ai_handler import encode_image_to_base64

    client = ai_client or AIClient()
    if not client.is_available():
        return None

    system_prompt = _build_filter_prompt(purchase_intent)
    product_json = _compact_product_json(record)
    user_text = f"{system_prompt}\n\n商品数据：\n```json\n{product_json}\n```"

    image_data_urls: List[str] = []
    for path in (image_paths or [])[: max(0, max_images)]:
        encoded = encode_image_to_base64(path)
        if encoded:
            image_data_urls.append(f"data:image/jpeg;base64,{encoded}")

    user_content = build_user_message_content(user_text, image_data_urls)
    messages = [{"role": "user", "content": user_content}]

    try:
        raw = await client._call_ai(
            messages,
            temperature=0.05,
            max_output_tokens=800,
            enable_json_output=ENABLE_RESPONSE_FORMAT,
        )
        parsed = parse_ai_response_json(raw)
        if not isinstance(parsed, dict):
            return None
        return _normalize_filter_response(parsed)
    except Exception as exc:
        print(f"   [AI品类过滤] 调用失败: {exc}")
        return None

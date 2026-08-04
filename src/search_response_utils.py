"""
闲鱼搜索 MTOP 响应解析与诊断（mtop.taobao.idlemtopsearch.pc.search）。
"""
from __future__ import annotations

import json
from typing import Any


def unwrap_mtop_data(payload: Any) -> dict:
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data")
    if isinstance(data, str):
        text = data.strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


def extract_search_result_list(payload: Any) -> list:
    data = unwrap_mtop_data(payload)
    items = data.get("resultList")
    if isinstance(items, list):
        return items
    return []


def summarize_search_payload(payload: Any, *, max_keys: int = 12) -> str:
    if not isinstance(payload, dict):
        return f"type={type(payload).__name__}"
    ret = payload.get("ret")
    data = unwrap_mtop_data(payload)
    keys = list(data.keys())[:max_keys] if isinstance(data, dict) else []
    items = data.get("resultList") if isinstance(data, dict) else None
    if isinstance(items, list):
        rl_info = str(len(items))
    elif items is None:
        rl_info = "missing"
    else:
        rl_info = f"non-list:{type(items).__name__}"
    return f"ret={ret!r}, data_keys={keys}, resultList={rl_info}"

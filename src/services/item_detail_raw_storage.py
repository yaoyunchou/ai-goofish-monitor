"""商品详情 API 完整响应归档（mtop.taobao.idle.pc.detail 等）。"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from src.config import DETAIL_API_URL_PATTERN
from src.infrastructure.persistence.db_connection import db_connection
from src.infrastructure.persistence.sql_dialect import json_text, parse_json_field
from src.infrastructure.persistence.storage_bootstrap import bootstrap_storage

DEFAULT_DETAIL_API_NAME = "mtop.taobao.idle.pc.detail"


def save_item_detail_api_raw_sync(
    *,
    item_id: str,
    raw_json: dict[str, Any],
    task_name: str,
    seller_user_id: str | None = None,
    source: str = "seller_subscription",
    api_name: str = DEFAULT_DETAIL_API_NAME,
    captured_at: str | None = None,
) -> int:
    """写入一条详情 API 原始响应，返回新行 id。"""
    bootstrap_storage()
    if not item_id or not raw_json:
        raise ValueError("item_id and raw_json are required")
    ts = captured_at or datetime.now().isoformat()
    with db_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO item_detail_api_raw (
                item_id, seller_user_id, task_name, source, api_name, raw_json, captured_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                str(item_id),
                seller_user_id,
                task_name,
                source,
                api_name,
                json_text(raw_json),
                ts,
            ),
        ).fetchone()
        conn.commit()
    return int(row["id"]) if row else 0


def get_latest_item_detail_api_raw_sync(
    item_id: str,
    *,
    task_name: str | None = None,
) -> dict[str, Any] | None:
    bootstrap_storage()
    conditions = ["item_id = ?"]
    params: list[Any] = [str(item_id)]
    if task_name:
        conditions.append("task_name = ?")
        params.append(task_name)
    sql = f"""
        SELECT id, item_id, seller_user_id, task_name, source, api_name, raw_json, captured_at
        FROM item_detail_api_raw
        WHERE {' AND '.join(conditions)}
        ORDER BY captured_at DESC, id DESC
        LIMIT 1
    """
    with db_connection() as conn:
        row = conn.execute(sql, params).fetchone()
    if not row:
        return None
    payload = dict(row)
    payload["raw_json"] = parse_json_field(payload.get("raw_json"), default={})
    return payload


def list_item_detail_api_raw_sync(
    item_id: str,
    *,
    task_name: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    bootstrap_storage()
    conditions = ["item_id = ?"]
    params: list[Any] = [str(item_id)]
    if task_name:
        conditions.append("task_name = ?")
        params.append(task_name)
    params.append(limit)
    sql = f"""
        SELECT id, item_id, seller_user_id, task_name, source, api_name, raw_json, captured_at
        FROM item_detail_api_raw
        WHERE {' AND '.join(conditions)}
        ORDER BY captured_at DESC, id DESC
        LIMIT ?
    """
    with db_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["raw_json"] = parse_json_field(payload.get("raw_json"), default={})
        results.append(payload)
    return results


def summarize_detail_api_raw(raw_json: dict[str, Any] | None) -> dict[str, Any]:
    """从 mtop 详情 API 响应提取关键统计，供详情页展示。"""
    if not raw_json:
        return {
            "has_detail_api": False,
            "api": DEFAULT_DETAIL_API_NAME,
            "sku_count": 0,
            "top_level_keys": [],
            "data_keys": [],
            "item_do_keys": [],
        }
    data = raw_json.get("data") if isinstance(raw_json.get("data"), dict) else {}
    item_do = data.get("itemDO") if isinstance(data.get("itemDO"), dict) else {}
    sku_list = item_do.get("skuList") or item_do.get("idleItemSkuList") or []
    if not isinstance(sku_list, list):
        sku_list = []
    return {
        "has_detail_api": True,
        "api": raw_json.get("api") or DEFAULT_DETAIL_API_NAME,
        "sku_count": len(sku_list),
        "top_level_keys": list(raw_json.keys()),
        "data_keys": list(data.keys()),
        "item_do_keys": list(item_do.keys()),
        "min_price": item_do.get("minPrice"),
        "max_price": item_do.get("maxPrice"),
        "sold_price": item_do.get("soldPrice"),
    }


async def save_item_detail_api_raw(**kwargs) -> int:
    return await asyncio.to_thread(lambda: save_item_detail_api_raw_sync(**kwargs))


async def get_latest_item_detail_api_raw(item_id: str, *, task_name: str | None = None) -> dict[str, Any] | None:
    return await asyncio.to_thread(get_latest_item_detail_api_raw_sync, item_id, task_name=task_name)


async def list_item_detail_api_raw(
    item_id: str,
    *,
    task_name: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(
        list_item_detail_api_raw_sync,
        item_id,
        task_name=task_name,
        limit=limit,
    )


def detail_api_name_from_pattern() -> str:
    """从拦截 URL 片段推导 API 名称。"""
    marker = "mtop."
    if marker in DETAIL_API_URL_PATTERN:
        return DETAIL_API_URL_PATTERN.split(marker, 1)[1]
    return DEFAULT_DETAIL_API_NAME

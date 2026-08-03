"""
结果商品收录与 SKU 快照。
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.infrastructure.persistence.database_config import is_postgres
from src.infrastructure.persistence.db_connection import db_connection
from src.infrastructure.persistence.sql_dialect import (
    insert_collected_item_sql,
    json_text,
    parse_json_field,
)
from src.infrastructure.persistence.storage_bootstrap import bootstrap_storage
from src.services.item_sku_fetch_service import fetch_item_skus


def _row_to_collection(row, record: Optional[dict] = None) -> Dict[str, Any]:
    sku_payload = {}
    if row["sku_json"]:
        try:
            sku_payload = parse_json_field(row["sku_json"], default={})
        except json.JSONDecodeError:
            sku_payload = {}
    return {
        "id": row["id"],
        "result_item_id": row["result_item_id"],
        "collected_at": row["collected_at"],
        "sku_fetch_status": row["sku_fetch_status"],
        "sku_fetched_at": row["sku_fetched_at"],
        "sku_error": row["sku_error"],
        "skus": sku_payload.get("skus") or [],
        "sku_meta": {
            key: sku_payload.get(key)
            for key in ("fetched_at", "raw_payload_count", "title_fragments")
            if sku_payload.get(key) is not None
        },
        "record": record,
    }


def _load_result_record_by_id(conn, result_item_id: int) -> Optional[dict]:
    row = conn.execute(
        "SELECT raw_json FROM result_items WHERE id = ?",
        (result_item_id,),
    ).fetchone()
    if row is None:
        return None
    return parse_json_field(row["raw_json"], default={})


def _find_result_item_id(conn, result_filename: str, item_id: str) -> Optional[int]:
    row = conn.execute(
        """
        SELECT id FROM result_items
        WHERE result_filename = ? AND item_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (result_filename, item_id),
    ).fetchone()
    return int(row["id"]) if row else None


async def collect_result_item(
    *,
    result_item_id: Optional[int] = None,
    result_filename: Optional[str] = None,
    item_id: Optional[str] = None,
    fetch_skus: bool = True,
) -> Dict[str, Any]:
    collection_id = await asyncio.to_thread(
        _upsert_collection_sync,
        result_item_id,
        result_filename,
        item_id,
    )
    if fetch_skus:
        asyncio.create_task(refresh_collection_skus(collection_id))
    return await get_collection(collection_id) or {}


def _upsert_collection_sync(
    result_item_id: Optional[int],
    result_filename: Optional[str],
    item_id: Optional[str],
) -> int:
    bootstrap_storage()
    with db_connection() as conn:
        resolved_id = result_item_id
        if resolved_id is None:
            if not result_filename or not item_id:
                raise ValueError("需要提供 result_item_id 或 result_filename + item_id。")
            resolved_id = _find_result_item_id(conn, result_filename, item_id)
        if resolved_id is None:
            raise ValueError("未找到对应的结果商品。")

        existing = conn.execute(
            "SELECT id FROM collected_items WHERE result_item_id = ?",
            (resolved_id,),
        ).fetchone()
        if existing:
            return int(existing["id"])

        now = datetime.now().isoformat()
        cursor = conn.execute(
            insert_collected_item_sql(),
            (resolved_id, now),
        )
        conn.commit()
        if is_postgres():
            row = cursor.fetchone()
            return int(row["id"])
        return int(cursor.lastrowid)


async def list_collections() -> List[Dict[str, Any]]:
    return await asyncio.to_thread(_list_collections_sync)


def _list_collections_sync() -> List[Dict[str, Any]]:
    bootstrap_storage()
    items: List[Dict[str, Any]] = []
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.*, r.title, r.price_display, r.link, r.item_id, r.result_filename
            FROM collected_items c
            JOIN result_items r ON r.id = c.result_item_id
            ORDER BY c.collected_at DESC
            """
        ).fetchall()
        for row in rows:
            record = _load_result_record_by_id(conn, int(row["result_item_id"]))
            payload = _row_to_collection(row, record)
            payload["summary"] = {
                "title": row["title"],
                "price_display": row["price_display"],
                "link": row["link"],
                "item_id": row["item_id"],
                "result_filename": row["result_filename"],
            }
            items.append(payload)
    return items


async def get_collection(collection_id: int) -> Optional[Dict[str, Any]]:
    return await asyncio.to_thread(_get_collection_sync, collection_id)


def _get_collection_sync(collection_id: int) -> Optional[Dict[str, Any]]:
    bootstrap_storage()
    with db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM collected_items WHERE id = ?",
            (collection_id,),
        ).fetchone()
        if row is None:
            return None
        record = _load_result_record_by_id(conn, int(row["result_item_id"]))
        result_row = conn.execute(
            """
            SELECT title, link, item_id, result_filename, price_display
            FROM result_items WHERE id = ?
            """,
            (row["result_item_id"],),
        ).fetchone()
    payload = _row_to_collection(row, record)
    if result_row:
        payload["summary"] = dict(result_row)
    return payload


async def delete_collection(collection_id: int) -> bool:
    return await asyncio.to_thread(_delete_collection_sync, collection_id)


def _delete_collection_sync(collection_id: int) -> bool:
    bootstrap_storage()
    with db_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM collected_items WHERE id = ?",
            (collection_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


async def refresh_collection_skus(collection_id: int) -> Dict[str, Any]:
    bootstrap_storage()
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT c.id, c.result_item_id, r.link, r.title
            FROM collected_items c
            JOIN result_items r ON r.id = c.result_item_id
            WHERE c.id = ?
            """,
            (collection_id,),
        ).fetchone()
        if row is None:
            raise ValueError("收录记录不存在。")
        conn.execute(
            "UPDATE collected_items SET sku_fetch_status = 'running', sku_error = NULL WHERE id = ?",
            (collection_id,),
        )
        conn.commit()

    link = str(row["link"] or "")
    title = str(row["title"] or "")
    try:
        sku_payload = await fetch_item_skus(link, title=title)
        status = "done"
        error = None
    except Exception as exc:
        sku_payload = {"skus": [], "fetched_at": datetime.now().isoformat()}
        status = "failed"
        error = str(exc)

    with db_connection() as conn:
        conn.execute(
            """
            UPDATE collected_items
            SET sku_fetch_status = ?, sku_fetched_at = ?, sku_json = ?, sku_error = ?
            WHERE id = ?
            """,
            (
                status,
                datetime.now().isoformat(),
                json_text(sku_payload),
                error,
                collection_id,
            ),
        )
        conn.commit()

    result = await get_collection(collection_id)
    return result or {}


def lookup_result_item_id(result_filename: str, item_id: str) -> Optional[int]:
    bootstrap_storage()
    with db_connection() as conn:
        return _find_result_item_id(conn, result_filename, item_id)

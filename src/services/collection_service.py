"""
结果商品收录与 SKU 快照。
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

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
            for key in ("fetched_at", "raw_payload_count", "title_fragments", "fetch_method", "item_id")
            if sku_payload.get(key) is not None
        },
        "detail_data": sku_payload.get("detail_data") or {},
        "item_labels": parse_json_field(row["item_labels"], default=[]) if "item_labels" in row.keys() else [],
        "common_tags": parse_json_field(row["common_tags"], default=[]) if "common_tags" in row.keys() else [],
        "seller_id": row["seller_id"] if "seller_id" in row.keys() else None,
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
    from src.utils import log_time
    log_time(f"[收录] 收录请求 result_item_id={result_item_id} item_id={item_id}")
    collection_id = await asyncio.to_thread(
        _upsert_collection_sync,
        result_item_id,
        result_filename,
        item_id,
    )
    log_time(f"[收录] 已创建/找到 collection_id={collection_id}")
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
        row = cursor.fetchone()
        return int(row["id"])


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
    from src.utils import log_time
    log_time(f"[收录] 刷新SKU collection_id={collection_id} link={link} title={title[:30]}")
    try:
        sku_payload = await fetch_item_skus(link, title=title)
        status = "done"
        error = None
        log_time(f"[收录] 刷新完成 status=done method={sku_payload.get('fetch_method')} skus={len(sku_payload.get('skus', []))}")
    except Exception as exc:
        sku_payload = {"skus": [], "fetched_at": datetime.now().isoformat()}
        status = "failed"
        error = str(exc)
        log_time(f"[收录] 刷新失败: {type(exc).__name__}: {exc}")

    # 从 detail_data 提取结构化标签/分类，存入独立列便于查询
    item_labels: List[Dict[str, str]] = []
    common_tags: List[str] = []
    seller_id: Optional[str] = None
    detail_data = sku_payload.get("detail_data") or {}
    item_do = detail_data.get("itemDO") or {}
    seller_do = detail_data.get("sellerDO") or {}
    track_params = detail_data.get("trackParams") or {}
    if item_do:
        ext = item_do.get("itemLabelExtList") or []
        cpv = item_do.get("cpvLabels") or []
        seen = set()
        for entry in [*ext, *cpv]:
            label = entry.get("propertyText") or entry.get("propertyName") or ""
            value = entry.get("valueText") or entry.get("valueName") or ""
            if not label or not value:
                continue
            key = f"{label}:{value}"
            if key in seen:
                continue
            seen.add(key)
            item_labels.append({"label": label, "value": value})
        for tag in item_do.get("commonTags") or []:
            text = tag.get("text") if isinstance(tag, dict) else str(tag)
            if text:
                common_tags.append(text)
    if seller_do:
        seller_id = str(seller_do.get("pageUserId") or seller_do.get("userId") or seller_do.get("sellerId") or "") or None

    # 提取更多结构化字段
    _title = item_do.get("title") or ""
    _sold_price = str(item_do.get("soldPrice") or "")
    _original_price = str(item_do.get("originalPrice") or "")
    _want_cnt = item_do.get("wantCnt")
    _browse_cnt = item_do.get("browseCnt")
    _collect_cnt = item_do.get("collectCnt")
    _sold_cnt = item_do.get("soldCnt")
    _quantity = item_do.get("quantity")
    _category_id = str(item_do.get("categoryId") or track_params.get("categoryId") or "")
    _image_infos = item_do.get("imageInfos") or []
    _main_pic = (_image_infos[0].get("url") if _image_infos else "") or track_params.get("mainPic") or ""
    _image_count = len(_image_infos)
    _sku_list = item_do.get("skuList") or item_do.get("idleItemSkuList") or []
    _sku_count = len(_sku_list)
    _seller_name = seller_do.get("uniqueName") or seller_do.get("nick") or ""
    _seller_city = seller_do.get("city") or ""
    _seller_sold = seller_do.get("hasSoldNumInteger")
    _seller_item_count = seller_do.get("itemCount")
    _seller_good_rate = seller_do.get("newGoodRatioRate") or ""
    _seller_reg_days = seller_do.get("userRegDay")

    if item_labels or common_tags or seller_id:
        log_time(f"[收录] 提取结构化字段 labels={len(item_labels)} tags={len(common_tags)} seller={seller_id} sku={_sku_count} img={_image_count}")

    with db_connection() as conn:
        conn.execute(
            """
            UPDATE collected_items
            SET sku_fetch_status = ?, sku_fetched_at = ?, sku_json = ?, sku_error = ?,
                item_labels = ?, common_tags = ?, seller_id = ?,
                title = ?, sold_price = ?, original_price = ?,
                want_cnt = ?, browse_cnt = ?, collect_cnt = ?, sold_cnt = ?, quantity_cnt = ?,
                category_id = ?, main_pic_url = ?, image_count = ?, sku_count = ?,
                seller_name = ?, seller_city = ?, seller_sold_cnt = ?, seller_item_count = ?,
                seller_good_rate = ?, seller_register_days = ?
            WHERE id = ?
            """,
            (
                status,
                datetime.now().isoformat(),
                json_text(sku_payload),
                error,
                json_text(item_labels),
                json_text(common_tags),
                seller_id,
                _title or None,
                _sold_price or None,
                _original_price or None,
                _want_cnt,
                _browse_cnt,
                _collect_cnt,
                _sold_cnt,
                _quantity,
                _category_id or None,
                _main_pic or None,
                _image_count if _image_count else None,
                _sku_count if _sku_count else None,
                _seller_name or None,
                _seller_city or None,
                _seller_sold,
                _seller_item_count,
                _seller_good_rate or None,
                _seller_reg_days,
                collection_id,
            ),
        )
        conn.commit()

    # 将 detail_data 拆分写入 goofish_ 规范化表
    if detail_data:
        try:
            from src.services.detail_normalizer import normalize_and_save_detail
            normalize_and_save_detail(detail_data, collection_id)
        except Exception as exc:
            log_time(f"[收录] 规范化写入失败(不影响主流程): {type(exc).__name__}: {exc}")

    result = await get_collection(collection_id)
    return result or {}


def lookup_result_item_id(result_filename: str, item_id: str) -> Optional[int]:
    bootstrap_storage()
    with db_connection() as conn:
        return _find_result_item_id(conn, result_filename, item_id)

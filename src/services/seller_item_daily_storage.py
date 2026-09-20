"""卖家订阅商品日级指标 + 通用爬虫原始数据存储。"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any

from src.infrastructure.persistence.db_connection import db_connection
from src.infrastructure.persistence.sql_dialect import json_text, parse_json_field
from src.infrastructure.persistence.storage_bootstrap import bootstrap_storage
from src.services.price_history_service import parse_price_value
from src.time_utils import SHANGHAI_TZ, shanghai_now_iso, shanghai_today, to_shanghai_iso

__all__ = [
    "SHANGHAI_TZ",
    "shanghai_now_iso",
    "shanghai_today",
    "to_shanghai_iso",
    "list_item_ids_with_daily_snapshot",
    "list_item_ids_with_daily_snapshot_sync",
    "upsert_seller_item_daily_snapshot",
    "upsert_seller_item_daily_snapshot_sync",
    "weekly_item_growth",
    "weekly_item_growth_sync",
    "load_muted_item_ids",
    "load_muted_item_ids_sync",
    "mute_items",
    "mute_items_sync",
    "unmute_item",
    "unmute_item_sync",
]


def upsert_seller_item_daily_snapshot_sync(
    *,
    task_name: str,
    seller_user_id: str,
    item: dict[str, Any],
    crawl_record: dict[str, Any],
    detail_api_raw: dict[str, Any] | None = None,
    snapshot_day: date | None = None,
) -> dict[str, Any]:
    """
    同事务写入：静态主表 + crawl_raw_records + seller_item_daily_metrics。

    同日再次采集：覆盖 raw_json / updated_at 与 want/view，不新增 raw 行（保持 1:1）。
    """
    bootstrap_storage()
    item_id = str(item.get("商品ID") or item.get("item_id") or "")
    if not item_id:
        raise ValueError("item_id is required")

    day = snapshot_day or shanghai_today()
    captured_at = shanghai_now_iso()
    title = item.get("商品标题") or item.get("title")
    price = parse_price_value(item.get("当前售价") or item.get("商品价格") or item.get("price"))
    item_status = item.get("商品状态") or item.get("item_status")
    item_link = item.get("商品链接") or item.get("item_link") or ""
    main_image = item.get("商品主图链接") or item.get("商品主图") or item.get("main_image")
    want_count = item.get("_want_count")
    view_count = item.get("_view_count")
    raw_payload = {
        "crawl_record": crawl_record,
        "detail_api_raw": detail_api_raw if isinstance(detail_api_raw, dict) else None,
    }

    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO seller_subscription_items (
                task_name, seller_user_id, item_id, title, price, item_status,
                item_link, main_image, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (task_name, seller_user_id, item_id) DO UPDATE SET
                title = EXCLUDED.title,
                price = EXCLUDED.price,
                item_status = EXCLUDED.item_status,
                item_link = EXCLUDED.item_link,
                main_image = EXCLUDED.main_image,
                last_seen_at = EXCLUDED.last_seen_at
            """,
            (
                task_name,
                seller_user_id,
                item_id,
                title,
                price,
                item_status,
                item_link,
                main_image,
                captured_at,
                captured_at,
            ),
        )

        existing = conn.execute(
            """
            SELECT id, raw_record_id
            FROM seller_item_daily_metrics
            WHERE task_name = ? AND seller_user_id = ? AND item_id = ? AND snapshot_day = ?
            """,
            (task_name, seller_user_id, item_id, day.isoformat()),
        ).fetchone()

        if existing:
            raw_id = int(existing["raw_record_id"])
            conn.execute(
                """
                UPDATE crawl_raw_records
                SET raw_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (json_text(raw_payload), captured_at, raw_id),
            )
            conn.execute(
                """
                UPDATE seller_item_daily_metrics
                SET want_count = ?, view_count = ?, captured_at = ?
                WHERE id = ?
                """,
                (want_count, view_count, captured_at, int(existing["id"])),
            )
            metrics_id = int(existing["id"])
        else:
            raw_row = conn.execute(
                """
                INSERT INTO crawl_raw_records (created_at, updated_at, raw_json)
                VALUES (?, ?, ?)
                RETURNING id
                """,
                (captured_at, captured_at, json_text(raw_payload)),
            ).fetchone()
            raw_id = int(raw_row["id"])
            metrics_row = conn.execute(
                """
                INSERT INTO seller_item_daily_metrics (
                    task_name, seller_user_id, item_id, snapshot_day,
                    want_count, view_count, captured_at, raw_record_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    task_name,
                    seller_user_id,
                    item_id,
                    day.isoformat(),
                    want_count,
                    view_count,
                    captured_at,
                    raw_id,
                ),
            ).fetchone()
            metrics_id = int(metrics_row["id"])

        conn.commit()

    return {
        "metrics_id": metrics_id,
        "raw_record_id": raw_id,
        "snapshot_day": day.isoformat(),
        "item_id": item_id,
    }


async def upsert_seller_item_daily_snapshot(**kwargs) -> dict[str, Any]:
    return await asyncio.to_thread(lambda: upsert_seller_item_daily_snapshot_sync(**kwargs))


def list_item_ids_with_daily_snapshot_sync(
    *,
    task_name: str,
    seller_user_id: str,
    item_ids: list[str],
    snapshot_day: date | None = None,
) -> set[str]:
    """返回指定自然日已有日指标的商品 ID 集合。"""
    normalized = [str(item_id).strip() for item_id in item_ids if str(item_id).strip()]
    if not normalized:
        return set()
    day = snapshot_day or shanghai_today()
    bootstrap_storage()
    placeholders = ", ".join("?" for _ in normalized)
    sql = f"""
        SELECT item_id
        FROM seller_item_daily_metrics
        WHERE task_name = ? AND seller_user_id = ? AND snapshot_day = ?
          AND item_id IN ({placeholders})
    """
    with db_connection() as conn:
        rows = conn.execute(
            sql,
            [task_name, seller_user_id, day.isoformat(), *normalized],
        ).fetchall()
    return {str(row["item_id"]) for row in rows}


async def list_item_ids_with_daily_snapshot(**kwargs) -> set[str]:
    return await asyncio.to_thread(lambda: list_item_ids_with_daily_snapshot_sync(**kwargs))


def _row_to_legacy_metric(row: dict[str, Any]) -> dict[str, Any]:
    """将日指标 JOIN 结果映射为旧 API 形状（含 snapshot_time / title / price）。"""
    snapshot_day = row.get("snapshot_day")
    if hasattr(snapshot_day, "isoformat"):
        snapshot_day = snapshot_day.isoformat()
    captured = to_shanghai_iso(row.get("captured_at"))
    return {
        "task_name": row.get("task_name"),
        "seller_user_id": row.get("seller_user_id"),
        "item_id": row.get("item_id"),
        "title": row.get("title"),
        "price": row.get("price"),
        "item_status": row.get("item_status"),
        "want_count": row.get("want_count"),
        "view_count": row.get("view_count"),
        "snapshot_time": captured or snapshot_day,
        "snapshot_day": snapshot_day,
        "raw_record_id": row.get("raw_record_id"),
        "item_link": row.get("item_link"),
        "main_image": row.get("main_image"),
    }


_LATEST_JOIN_SQL = """
    SELECT
        m.task_name,
        m.seller_user_id,
        m.item_id,
        m.want_count,
        m.view_count,
        m.captured_at,
        m.snapshot_day,
        m.raw_record_id,
        i.title,
        i.price,
        i.item_status,
        i.item_link,
        i.main_image
    FROM seller_item_daily_metrics m
    LEFT JOIN seller_subscription_items i
        ON i.task_name = m.task_name
       AND i.seller_user_id = m.seller_user_id
       AND i.item_id = m.item_id
"""


def _latest_daily_inner_sql(conditions: list[str]) -> str:
    where = " AND ".join(conditions)
    return f"""
        SELECT DISTINCT ON (m.item_id)
            m.task_name, m.seller_user_id, m.item_id,
            m.want_count, m.view_count, m.captured_at, m.snapshot_day, m.raw_record_id,
            i.title, i.price, i.item_status, i.item_link, i.main_image
        FROM seller_item_daily_metrics m
        LEFT JOIN seller_subscription_items i
            ON i.task_name = m.task_name
           AND i.seller_user_id = m.seller_user_id
           AND i.item_id = m.item_id
        WHERE {where}
        ORDER BY m.item_id, m.snapshot_day DESC, m.captured_at DESC
    """


_ITEM_SORT_COLUMNS = {
    "price": "price",
    "want_count": "want_count",
    "view_count": "view_count",
    "snapshot_time": "captured_at",
}

# 商品列表/计数只展示仍在订阅表中的卖家，避免删订阅后孤儿日指标继续出现在 UI。
SQL_ITEM_BELONGS_TO_SUBSCRIPTION = (
    "EXISTS (SELECT 1 FROM seller_subscriptions s WHERE s.seller_user_id = m.seller_user_id)"
)


def list_item_daily_metrics_sync(
    task_name: str,
    item_id: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """趋势：按 snapshot_day 倒序（一日一点）。"""
    bootstrap_storage()
    conditions = ["m.task_name = ?"]
    params: list[Any] = [task_name]
    if item_id:
        conditions.append("m.item_id = ?")
        params.append(item_id)
    sql = f"""
        {_LATEST_JOIN_SQL}
        WHERE {' AND '.join(conditions)}
        ORDER BY m.snapshot_day DESC, m.captured_at DESC
        LIMIT ?
    """
    params.append(limit)
    with db_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_legacy_metric(dict(row)) for row in rows]


def list_latest_item_daily_metrics_sync(
    task_name: str,
    seller_user_id: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    bootstrap_storage()
    conditions = ["m.task_name = ?", SQL_ITEM_BELONGS_TO_SUBSCRIPTION]
    params: list[Any] = [task_name]
    if seller_user_id:
        conditions.append("m.seller_user_id = ?")
        params.append(seller_user_id)
    sql = f"""
        {_latest_daily_inner_sql(conditions)}
        LIMIT ?
    """
    params.append(limit)
    with db_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    metrics = [_row_to_legacy_metric(dict(row)) for row in rows]
    metrics.sort(key=lambda row: row.get("snapshot_time") or "", reverse=True)
    return metrics


def list_latest_item_daily_metrics_paginated_sync(
    task_name: str,
    seller_user_id: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "snapshot_time",
    sort_order: str = "desc",
) -> list[dict[str, Any]]:
    bootstrap_storage()
    conditions = ["m.task_name = ?", SQL_ITEM_BELONGS_TO_SUBSCRIPTION]
    params: list[Any] = [task_name]
    if seller_user_id:
        conditions.append("m.seller_user_id = ?")
        params.append(seller_user_id)
    inner = _latest_daily_inner_sql(conditions)
    filter_sql = ""
    filter_params: list[Any] = []
    if search:
        filter_sql = " WHERE title ILIKE ?"
        filter_params.append(f"%{search}%")
    order_col = _ITEM_SORT_COLUMNS.get(sort_by, "captured_at")
    direction = "ASC" if str(sort_order).lower() == "asc" else "DESC"
    nulls = "" if order_col == "captured_at" else " NULLS LAST"
    sql = f"""
        SELECT * FROM ({inner}) latest
        {filter_sql}
        ORDER BY {order_col} {direction}{nulls}
        LIMIT ? OFFSET ?
    """
    offset = max(page - 1, 0) * page_size
    with db_connection() as conn:
        rows = conn.execute(sql, params + filter_params + [page_size, offset]).fetchall()
    return [_row_to_legacy_metric(dict(row)) for row in rows]


def count_latest_item_daily_metrics_sync(
    task_name: str,
    seller_user_id: str | None = None,
    search: str | None = None,
) -> int:
    bootstrap_storage()
    conditions = ["m.task_name = ?", SQL_ITEM_BELONGS_TO_SUBSCRIPTION]
    params: list[Any] = [task_name]
    if seller_user_id:
        conditions.append("m.seller_user_id = ?")
        params.append(seller_user_id)
    inner = _latest_daily_inner_sql(conditions)
    filter_sql = ""
    filter_params: list[Any] = []
    if search:
        filter_sql = " WHERE title ILIKE ?"
        filter_params.append(f"%{search}%")
    sql = f"SELECT COUNT(*) AS total FROM ({inner}) latest{filter_sql}"
    with db_connection() as conn:
        row = conn.execute(sql, params + filter_params).fetchone()
    return int(row["total"]) if row else 0


def get_item_detail_from_daily_sync(task_name: str, item_id: str) -> dict[str, Any]:
    """详情：日指标趋势 + 最新日原始 JSON（crawl_record / detail_api_raw）。"""
    from src.services.item_detail_raw_storage import summarize_detail_api_raw

    bootstrap_storage()
    metrics = list_item_daily_metrics_sync(task_name, item_id=item_id, limit=200)

    record: dict[str, Any] | None = None
    detail_api_raw: dict[str, Any] | None = None
    raw_record_id: int | None = None
    crawl_time: str | None = None
    snapshot_day: str | None = None

    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT m.raw_record_id, m.snapshot_day, m.captured_at, r.raw_json, r.updated_at
            FROM seller_item_daily_metrics m
            JOIN crawl_raw_records r ON r.id = m.raw_record_id
            WHERE m.task_name = ? AND m.item_id = ?
            ORDER BY m.snapshot_day DESC, m.captured_at DESC
            LIMIT 1
            """,
            (task_name, item_id),
        ).fetchone()

    if row:
        raw_record_id = int(row["raw_record_id"])
        day = row.get("snapshot_day")
        snapshot_day = day.isoformat() if hasattr(day, "isoformat") else str(day) if day else None
        updated = row.get("updated_at") or row.get("captured_at")
        crawl_time = updated.isoformat() if hasattr(updated, "isoformat") else str(updated) if updated else None
        payload = parse_json_field(row.get("raw_json"), default={})
        if isinstance(payload, dict):
            crawl = payload.get("crawl_record")
            record = crawl if isinstance(crawl, dict) else payload
            detail = payload.get("detail_api_raw")
            detail_api_raw = detail if isinstance(detail, dict) else None

    from src.services.seller_subscription_storage import _summarize_subscription_record

    record_summary = _summarize_subscription_record(record)
    api_summary = summarize_detail_api_raw(detail_api_raw)
    record_summary["has_sku_data"] = record_summary.get("has_sku_data") or api_summary.get("sku_count", 0) > 0

    detail_api_row = None
    if detail_api_raw is not None:
        detail_api_row = {
            "id": raw_record_id,
            "item_id": item_id,
            "task_name": task_name,
            "source": "seller_subscription",
            "api_name": detail_api_raw.get("api") or "mtop.taobao.idle.pc.detail",
            "raw_json": detail_api_raw,
            "captured_at": crawl_time,
            "snapshot_day": snapshot_day,
        }

    return {
        "item_id": item_id,
        "result_filename": None,
        "result_item_id": raw_record_id,
        "crawl_time": crawl_time,
        "snapshot_day": snapshot_day,
        "metrics": metrics,
        "record": record,
        "detail_api": detail_api_row,
        "detail_api_summary": api_summary,
        "data_summary": record_summary,
    }


async def list_item_daily_metrics(task_name: str, item_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    return await asyncio.to_thread(list_item_daily_metrics_sync, task_name, item_id, limit)


async def list_latest_item_daily_metrics(
    task_name: str,
    seller_user_id: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(list_latest_item_daily_metrics_sync, task_name, seller_user_id, limit)


async def list_latest_item_daily_metrics_paginated(**kwargs) -> list[dict[str, Any]]:
    return await asyncio.to_thread(lambda: list_latest_item_daily_metrics_paginated_sync(**kwargs))


async def count_latest_item_daily_metrics(**kwargs) -> int:
    return await asyncio.to_thread(lambda: count_latest_item_daily_metrics_sync(**kwargs))


async def get_item_detail_from_daily(task_name: str, item_id: str) -> dict[str, Any]:
    return await asyncio.to_thread(get_item_detail_from_daily_sync, task_name, item_id)


# ---------------------------------------------------------------------------
# 商品级周增长聚合（监控健康度自动停用用）
# ---------------------------------------------------------------------------

_WEEKLY_GROWTH_SQL = """
    WITH first_seen AS (
        SELECT DISTINCT ON (m.seller_user_id, m.item_id)
               m.seller_user_id, m.item_id, m.snapshot_day,
               m.view_count, m.want_count
        FROM seller_item_daily_metrics m
        WHERE m.snapshot_day BETWEEN ? AND ?
        ORDER BY m.seller_user_id, m.item_id, m.snapshot_day ASC, m.captured_at ASC
    ),
    last_seen AS (
        SELECT DISTINCT ON (m.seller_user_id, m.item_id)
               m.seller_user_id, m.item_id, m.snapshot_day,
               m.view_count, m.want_count
        FROM seller_item_daily_metrics m
        WHERE m.snapshot_day BETWEEN ? AND ?
        ORDER BY m.seller_user_id, m.item_id, m.snapshot_day DESC, m.captured_at DESC
    ),
    span AS (
        SELECT m.seller_user_id, m.item_id,
               COUNT(*)          AS days_with_data,
               MIN(m.snapshot_day) AS first_day,
               MAX(m.snapshot_day) AS last_day
        FROM seller_item_daily_metrics m
        WHERE m.snapshot_day BETWEEN ? AND ?
        GROUP BY m.seller_user_id, m.item_id
    )
    SELECT f.seller_user_id,
           f.item_id,
           s.days_with_data,
           s.first_day,
           s.last_day,
           f.view_count AS view_start,
           l.view_count AS view_end,
           COALESCE(l.view_count, 0) - COALESCE(f.view_count, 0) AS view_growth,
           f.want_count AS want_start,
           l.want_count AS want_end,
           COALESCE(l.want_count, 0) - COALESCE(f.want_count, 0) AS want_growth,
           i.title,
           i.price,
           i.item_status,
           i.item_link,
           i.first_seen_at,
           COALESCE(i.is_muted, FALSE) AS is_muted
    FROM first_seen f
    JOIN last_seen l USING (seller_user_id, item_id)
    JOIN span      s USING (seller_user_id, item_id)
    LEFT JOIN seller_subscription_items i
           ON i.seller_user_id = f.seller_user_id
          AND i.item_id = f.item_id
"""


def _to_iso_date(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def weekly_item_growth_sync(
    week_start: date,
    week_end: date,
) -> list[dict[str, Any]]:
    """按「卖家 + 商品」聚合一自然周内的浏览/想要增长。

    增长 = 窗口内最后一天的值 - 窗口内第一天的值。
    只返回窗口内 **至少跨 2 天** 的商品（单天数据无法算增长，直接排除）。

    边界约定：
      - want_count / view_count 为 NULL 时按 0 参与差值（COALESCE），
        但 `has_metric_data` 会标记首末是否都有真实值，供判定层决定是否跳过。
      - `last_day` 由调用方与 `week_end` 比较，用于识别「数据中断」。
    """
    bootstrap_storage()
    params = (
        week_start.isoformat(),
        week_end.isoformat(),
        week_start.isoformat(),
        week_end.isoformat(),
        week_start.isoformat(),
        week_end.isoformat(),
    )
    with db_connection() as conn:
        rows = conn.execute(_WEEKLY_GROWTH_SQL, params).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        first_day = _to_iso_date(payload.get("first_day"))
        last_day = _to_iso_date(payload.get("last_day"))
        # 仅在首末都不是同一天时才计入（防御性校验，SQL 已过滤）
        if not first_day or not last_day or first_day >= last_day:
            continue
        payload["first_day"] = first_day
        payload["last_day"] = last_day
        payload["days_with_data"] = int(payload.get("days_with_data") or 0)
        payload["view_start"] = payload.get("view_start")
        payload["view_end"] = payload.get("view_end")
        payload["want_start"] = payload.get("want_start")
        payload["want_end"] = payload.get("want_end")
        payload["view_growth"] = int(payload.get("view_growth") or 0)
        payload["want_growth"] = int(payload.get("want_growth") or 0)
        payload["is_muted"] = bool(payload.get("is_muted"))
        payload["has_metric_data"] = (
            payload["view_start"] is not None
            and payload["view_end"] is not None
            and payload["want_start"] is not None
            and payload["want_end"] is not None
        )
        first_seen_at = payload.get("first_seen_at")
        payload["first_seen_at"] = (
            first_seen_at.isoformat() if hasattr(first_seen_at, "isoformat") else first_seen_at
        )
        results.append(payload)
    return results


async def weekly_item_growth(week_start: date, week_end: date) -> list[dict[str, Any]]:
    return await asyncio.to_thread(weekly_item_growth_sync, week_start, week_end)


def load_muted_item_ids_sync(seller_user_id: str) -> set[str]:
    """返回该卖家下已被停用监控的商品 ID 集合，供采集阶段过滤。"""
    bootstrap_storage()
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT item_id
            FROM seller_subscription_items
            WHERE seller_user_id = ? AND is_muted = TRUE
            """,
            (seller_user_id,),
        ).fetchall()
    return {str(row["item_id"]) for row in rows}


async def load_muted_item_ids(seller_user_id: str) -> set[str]:
    return await asyncio.to_thread(load_muted_item_ids_sync, seller_user_id)


def mute_items_sync(
    items: list[dict[str, Any]],
    *,
    reason: str,
    week_start: date,
) -> int:
    """批量标记商品为「已停止监控」。items 需含 seller_user_id + item_id。"""
    if not items:
        return 0
    bootstrap_storage()
    muted_at = shanghai_now_iso()
    updated = 0
    with db_connection() as conn:
        for item in items:
            cursor = conn.execute(
                """
                UPDATE seller_subscription_items
                SET is_muted = TRUE,
                    muted_at = ?,
                    muted_reason = ?,
                    muted_week = ?
                WHERE seller_user_id = ? AND item_id = ?
                """,
                (
                    muted_at,
                    reason,
                    week_start.isoformat(),
                    str(item.get("seller_user_id")),
                    str(item.get("item_id")),
                ),
            )
            updated += cursor.rowcount or 0
        conn.commit()
    return updated


async def mute_items(items: list[dict[str, Any]], **kwargs) -> int:
    return await asyncio.to_thread(lambda: mute_items_sync(items, **kwargs))


def unmute_item_sync(seller_user_id: str, item_id: str) -> bool:
    """恢复单个商品的监控。"""
    bootstrap_storage()
    with db_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE seller_subscription_items
            SET is_muted = FALSE,
                muted_at = NULL,
                muted_reason = NULL,
                muted_week = NULL
            WHERE seller_user_id = ? AND item_id = ?
            """,
            (seller_user_id, item_id),
        )
        conn.commit()
        return (cursor.rowcount or 0) > 0


async def unmute_item(seller_user_id: str, item_id: str) -> bool:
    return await asyncio.to_thread(unmute_item_sync, seller_user_id, item_id)

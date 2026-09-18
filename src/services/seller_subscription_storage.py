"""订阅卖家画像与商品指标存储。"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from src.infrastructure.persistence.db_connection import db_connection
from src.infrastructure.persistence.sql_dialect import json_text, parse_json_field
from src.infrastructure.persistence.storage_bootstrap import bootstrap_storage
from src.domain.seller_ids import parse_metric_int, parse_praise_ratio
from src.services.price_history_service import parse_price_value
from src.time_utils import shanghai_now_iso, to_shanghai_iso

_SUBSCRIPTION_TIME_FIELDS = (
    "last_captured_at",
    "created_at",
    "profile_captured_at",
    "captured_at",
    "last_run_at",
)


def _normalize_time_fields(row: dict[str, Any], fields: tuple[str, ...] = _SUBSCRIPTION_TIME_FIELDS) -> dict[str, Any]:
    for key in fields:
        if key in row and row[key] is not None:
            row[key] = to_shanghai_iso(row[key])
    return row


def save_seller_profile_sync(task_name: str, seller_user_id: str, profile: dict) -> None:
    """按 Asia/Shanghai 自然日 UPSERT，同日覆盖 profile_json。"""
    from src.services.seller_item_daily_storage import shanghai_today

    bootstrap_storage()
    profile_day = shanghai_today()
    captured_at = shanghai_now_iso()
    with db_connection() as conn:
        existing = conn.execute(
            """
            SELECT id FROM seller_profiles
            WHERE task_name = ? AND seller_user_id = ? AND profile_day = ?
            """,
            (task_name, seller_user_id, profile_day.isoformat()),
        ).fetchone()
        values = (
            task_name,
            seller_user_id,
            profile.get("卖家昵称"),
            profile.get("鱼小铺等级"),
            parse_praise_ratio(profile.get("好评率")),
            parse_metric_int(profile.get("粉丝数")),
            parse_metric_int(profile.get("卖家在售/已售商品数")),
            parse_metric_int(profile.get("卖家收到的评价总数")),
            json_text(profile),
            captured_at,
            profile_day.isoformat(),
        )
        if existing:
            conn.execute(
                """
                UPDATE seller_profiles SET
                    nickname = ?, shop_level = ?, praise_ratio = ?,
                    followers = ?, item_count = ?, rating_count = ?,
                    profile_json = ?, captured_at = ?
                WHERE id = ?
                """,
                (
                    values[2],
                    values[3],
                    values[4],
                    values[5],
                    values[6],
                    values[7],
                    values[8],
                    values[9],
                    int(existing["id"]),
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO seller_profiles (
                    task_name, seller_user_id, nickname, shop_level, praise_ratio,
                    followers, item_count, rating_count, profile_json, captured_at, profile_day
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
        conn.commit()


def save_seller_item_metric_sync(
    *,
    task_name: str,
    seller_user_id: str,
    item: dict,
) -> None:
    bootstrap_storage()
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO seller_item_metrics (
                task_name, seller_user_id, item_id, title, price, item_status,
                want_count, view_count, snapshot_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_name,
                seller_user_id,
                str(item.get("商品ID") or ""),
                item.get("商品标题") or item.get("title"),
                parse_price_value(item.get("当前售价") or item.get("商品价格")),
                item.get("商品状态"),
                item.get("_want_count"),
                item.get("_view_count"),
                shanghai_now_iso(),
            ),
        )
        conn.commit()


async def save_seller_profile(task_name: str, seller_user_id: str, profile: dict) -> None:
    await asyncio.to_thread(save_seller_profile_sync, task_name, seller_user_id, profile)


async def save_seller_item_metric(**kwargs) -> None:
    await asyncio.to_thread(lambda: save_seller_item_metric_sync(**kwargs))


def list_latest_profiles_sync(task_name: str | None = None) -> list[dict[str, Any]]:
    bootstrap_storage()
    sql = """
        SELECT DISTINCT ON (seller_user_id)
            task_name, seller_user_id, nickname, shop_level, praise_ratio,
            followers, item_count, rating_count, profile_json, captured_at
        FROM seller_profiles
    """
    params: list = []
    if task_name:
        sql += " WHERE task_name = ?"
        params.append(task_name)
    sql += " ORDER BY seller_user_id, captured_at DESC"
    with db_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def list_item_metrics_sync(task_name: str, item_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    from src.services.seller_item_daily_storage import list_item_daily_metrics_sync

    daily = list_item_daily_metrics_sync(task_name, item_id=item_id, limit=limit)
    if daily:
        return daily
    # 兼容尚未 backfill 的历史库
    bootstrap_storage()
    conditions = ["task_name = ?"]
    params: list = [task_name]
    if item_id:
        conditions.append("item_id = ?")
        params.append(item_id)
    sql = f"""
        SELECT task_name, seller_user_id, item_id, title, price, item_status,
               want_count, view_count, snapshot_time
        FROM seller_item_metrics
        WHERE {' AND '.join(conditions)}
        ORDER BY snapshot_time DESC
        LIMIT ?
    """
    params.append(limit)
    with db_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


async def list_latest_profiles(task_name: str | None = None) -> list[dict[str, Any]]:
    return await asyncio.to_thread(list_latest_profiles_sync, task_name)


async def list_item_metrics(task_name: str, item_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    return await asyncio.to_thread(list_item_metrics_sync, task_name, item_id, limit)


def _summarize_subscription_record(record: dict[str, Any] | None) -> dict[str, Any]:
    """汇总爬虫原始记录字段，便于详情页取数测试。"""
    if not record:
        return {
            "has_record": False,
            "top_level_keys": [],
            "product_fields": [],
            "seller_fields": [],
            "image_count": 0,
            "description_length": 0,
            "has_sku_data": False,
        }
    product = record.get("商品信息") if isinstance(record.get("商品信息"), dict) else {}
    seller = record.get("卖家信息") if isinstance(record.get("卖家信息"), dict) else {}
    images = product.get("商品图片列表")
    image_list = images if isinstance(images, list) else []
    description = str(product.get("商品描述") or "")
    product_fields = list(product.keys())
    return {
        "has_record": True,
        "crawl_time": record.get("爬取时间"),
        "task_type": record.get("任务类型"),
        "task_name": record.get("任务名称"),
        "top_level_keys": list(record.keys()),
        "product_fields": product_fields,
        "seller_fields": list(seller.keys()),
        "image_count": len(image_list),
        "description_length": len(description),
        "has_sku_data": any(
            "sku" in str(key).lower() or "规格" in str(key)
            for key in product_fields
        ),
    }


def get_subscription_item_detail_sync(task_name: str, item_id: str) -> dict[str, Any]:
    """优先读日级表；若无日级数据则回退 result_items + item_detail_api_raw。"""
    from src.services.seller_item_daily_storage import get_item_detail_from_daily_sync

    daily = get_item_detail_from_daily_sync(task_name, item_id)
    if daily.get("metrics") or daily.get("record") or daily.get("detail_api"):
        return daily

    from src.infrastructure.persistence.storage_names import build_result_filename
    from src.services.item_detail_raw_storage import (
        get_latest_item_detail_api_raw_sync,
        summarize_detail_api_raw,
    )

    bootstrap_storage()
    result_filename = build_result_filename(task_name)
    metrics = list_item_metrics_sync(task_name, item_id=item_id, limit=200)
    record: dict[str, Any] | None = None
    result_item_id: int | None = None
    crawl_time: str | None = None

    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT id, crawl_time, raw_json
            FROM result_items
            WHERE item_id = ? AND result_filename = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (item_id, result_filename),
        ).fetchone()
        if row:
            result_item_id = int(row["id"])
            crawl_time = row.get("crawl_time")
            record = parse_json_field(row["raw_json"], default={})

    detail_api_row = get_latest_item_detail_api_raw_sync(item_id, task_name=task_name)
    detail_api_raw = detail_api_row.get("raw_json") if detail_api_row else None
    record_summary = _summarize_subscription_record(record)
    api_summary = summarize_detail_api_raw(detail_api_raw if isinstance(detail_api_raw, dict) else None)
    record_summary["has_sku_data"] = record_summary.get("has_sku_data") or api_summary.get("sku_count", 0) > 0

    return {
        "item_id": item_id,
        "result_filename": result_filename,
        "result_item_id": result_item_id,
        "crawl_time": crawl_time,
        "metrics": metrics,
        "record": record,
        "detail_api": detail_api_row,
        "detail_api_summary": api_summary,
        "data_summary": record_summary,
    }


async def get_subscription_item_detail(task_name: str, item_id: str) -> dict[str, Any]:
    return await asyncio.to_thread(get_subscription_item_detail_sync, task_name, item_id)


_ITEM_METRIC_COLUMNS = (
    "task_name, seller_user_id, item_id, title, price, item_status, "
    "want_count, view_count, snapshot_time"
)

_ITEM_SORT_COLUMNS = {
    "price": "price",
    "want_count": "want_count",
    "view_count": "view_count",
    "snapshot_time": "snapshot_time",
}


def _latest_item_metrics_inner_sql(conditions: list[str]) -> str:
    """每个商品最新快照的子查询（DISTINCT ON item_id）。"""
    return f"""
        SELECT DISTINCT ON (item_id) {_ITEM_METRIC_COLUMNS}
        FROM seller_item_metrics
        WHERE {' AND '.join(conditions)}
        ORDER BY item_id, snapshot_time DESC
    """


def _latest_item_metrics_filter_clause(search: str | None) -> tuple[str, list[Any]]:
    if not search:
        return "", []
    return " WHERE title ILIKE ?", [f"%{search}%"]


def list_latest_item_metrics_sync(
    task_name: str,
    seller_user_id: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    from src.services.seller_item_daily_storage import list_latest_item_daily_metrics_sync

    daily = list_latest_item_daily_metrics_sync(task_name, seller_user_id=seller_user_id, limit=limit)
    if daily:
        return daily
    bootstrap_storage()
    conditions = ["task_name = ?"]
    params: list[Any] = [task_name]
    if seller_user_id:
        conditions.append("seller_user_id = ?")
        params.append(seller_user_id)
    sql = f"""
        {_latest_item_metrics_inner_sql(conditions)}
        LIMIT ?
    """
    params.append(limit)
    with db_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    metrics = [dict(row) for row in rows]
    metrics.sort(key=lambda row: row.get("snapshot_time") or "", reverse=True)
    return metrics


def list_latest_item_metrics_paginated_sync(
    task_name: str,
    seller_user_id: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "snapshot_time",
    sort_order: str = "desc",
) -> list[dict[str, Any]]:
    from src.services.seller_item_daily_storage import (
        count_latest_item_daily_metrics_sync,
        list_latest_item_daily_metrics_paginated_sync,
    )

    daily_count = count_latest_item_daily_metrics_sync(
        task_name, seller_user_id=seller_user_id, search=search
    )
    if daily_count > 0:
        return list_latest_item_daily_metrics_paginated_sync(
            task_name,
            seller_user_id=seller_user_id,
            search=search,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    bootstrap_storage()
    conditions = ["task_name = ?"]
    params: list[Any] = [task_name]
    if seller_user_id:
        conditions.append("seller_user_id = ?")
        params.append(seller_user_id)
    inner = _latest_item_metrics_inner_sql(conditions)
    where, filter_params = _latest_item_metrics_filter_clause(search)
    order_col = _ITEM_SORT_COLUMNS.get(sort_by, "snapshot_time")
    direction = "ASC" if str(sort_order).lower() == "asc" else "DESC"
    nulls = "" if order_col == "snapshot_time" else " NULLS LAST"
    sql = f"""
        SELECT * FROM ({inner}) latest
        {where}
        ORDER BY {order_col} {direction}{nulls}
        LIMIT ? OFFSET ?
    """
    offset = max(page - 1, 0) * page_size
    with db_connection() as conn:
        rows = conn.execute(sql, params + filter_params + [page_size, offset]).fetchall()
    return [dict(row) for row in rows]


def count_latest_item_metrics_sync(
    task_name: str,
    seller_user_id: str | None = None,
    search: str | None = None,
) -> int:
    from src.services.seller_item_daily_storage import count_latest_item_daily_metrics_sync

    daily_count = count_latest_item_daily_metrics_sync(
        task_name, seller_user_id=seller_user_id, search=search
    )
    if daily_count > 0:
        return daily_count
    bootstrap_storage()
    conditions = ["task_name = ?"]
    params: list[Any] = [task_name]
    if seller_user_id:
        conditions.append("seller_user_id = ?")
        params.append(seller_user_id)
    inner = _latest_item_metrics_inner_sql(conditions)
    where, filter_params = _latest_item_metrics_filter_clause(search)
    sql = f"SELECT COUNT(*) AS total FROM ({inner}) latest{where}"
    with db_connection() as conn:
        row = conn.execute(sql, params + filter_params).fetchone()
    return int(row["total"]) if row else 0


def list_subscriptions_sync() -> list[dict[str, Any]]:
    from src.domain.seller_subscription import SELLER_SUBSCRIPTION_TASK_NAME

    bootstrap_storage()
    sql = """
        SELECT
            s.id,
            s.seller_user_id,
            s.seller_url,
            s.nickname,
            s.enabled,
            s.note,
            s.last_captured_at,
            s.created_at,
            p.nickname AS profile_nickname,
            p.shop_level,
            p.followers,
            p.item_count,
            p.captured_at AS profile_captured_at
        FROM seller_subscriptions s
        LEFT JOIN LATERAL (
            SELECT nickname, shop_level, followers, item_count, captured_at
            FROM seller_profiles
            WHERE task_name = ? AND seller_user_id = s.seller_user_id
            ORDER BY captured_at DESC
            LIMIT 1
        ) p ON TRUE
        ORDER BY s.created_at DESC
    """
    with db_connection() as conn:
        rows = conn.execute(sql, [SELLER_SUBSCRIPTION_TASK_NAME]).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["enabled"] = bool(item.get("enabled"))
        items.append(_normalize_time_fields(item))
    return items


def get_subscription_sync(subscription_id: int) -> dict[str, Any] | None:
    bootstrap_storage()
    with db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM seller_subscriptions WHERE id = ?",
            (subscription_id,),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["enabled"] = bool(result.get("enabled"))
    return result


def get_subscription_by_user_sync(seller_user_id: str) -> dict[str, Any] | None:
    bootstrap_storage()
    with db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM seller_subscriptions WHERE seller_user_id = ?",
            (seller_user_id,),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["enabled"] = bool(result.get("enabled"))
    return result


def get_latest_profile_sync(task_name: str, seller_user_id: str) -> dict[str, Any] | None:
    bootstrap_storage()
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT task_name, seller_user_id, nickname, shop_level, praise_ratio,
                   followers, item_count, rating_count, profile_json, captured_at
            FROM seller_profiles
            WHERE task_name = ? AND seller_user_id = ?
            ORDER BY captured_at DESC
            LIMIT 1
            """,
            (task_name, seller_user_id),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["profile_json"] = parse_json_field(result.get("profile_json"), default={})
    return _normalize_time_fields(result, ("captured_at",))


def add_subscription_sync(
    *,
    seller_user_id: str,
    seller_url: str | None,
    note: str | None,
) -> dict[str, Any]:
    bootstrap_storage()
    with db_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO seller_subscriptions (seller_user_id, seller_url, note)
            VALUES (?, ?, ?)
            ON CONFLICT (seller_user_id) DO UPDATE SET
                seller_url = COALESCE(EXCLUDED.seller_url, seller_subscriptions.seller_url),
                note = COALESCE(EXCLUDED.note, seller_subscriptions.note)
            RETURNING *
            """,
            (seller_user_id, seller_url, note or ""),
        ).fetchone()
        conn.commit()
    return dict(row)


def update_subscription_sync(subscription_id: int, **fields) -> dict[str, Any] | None:
    allowed = {"enabled", "note", "nickname", "last_captured_at"}
    updates = {key: fields[key] for key in allowed if key in fields}
    if not updates:
        return get_subscription_sync(subscription_id)
    set_clause = ", ".join(f"{key} = ?" for key in updates)
    params = list(updates.values()) + [subscription_id]
    bootstrap_storage()
    with db_connection() as conn:
        conn.execute(
            f"UPDATE seller_subscriptions SET {set_clause} WHERE id = ?",
            params,
        )
        conn.commit()
    return get_subscription_sync(subscription_id)


def delete_subscription_sync(subscription_id: int) -> bool:
    bootstrap_storage()
    with db_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM seller_subscriptions WHERE id = ?",
            (subscription_id,),
        )
        conn.commit()
    return cursor.rowcount > 0


def list_enabled_seller_ids_sync() -> list[str]:
    bootstrap_storage()
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT seller_user_id
            FROM seller_subscriptions
            WHERE enabled = TRUE
            ORDER BY created_at ASC
            """
        ).fetchall()
    return [str(row["seller_user_id"]) for row in rows]


def get_schedule_sync() -> dict[str, Any]:
    from src.domain.seller_ids import DEFAULT_SELLER_SUBSCRIPTION_ITEM_LIMIT
    from src.domain.seller_subscription import DEFAULT_SELLER_SUBSCRIPTION_CRON

    bootstrap_storage()
    with db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM seller_subscription_schedule WHERE id = 1"
        ).fetchone()
    if not row:
        return {
            "enabled": True,
            "cron": DEFAULT_SELLER_SUBSCRIPTION_CRON,
            "item_limit": DEFAULT_SELLER_SUBSCRIPTION_ITEM_LIMIT,
            "collect_ratings": False,
            "account_state_file": None,
            "account_strategy": "auto",
            "is_running": False,
            "pacing_json": None,
        }
    payload = dict(row)
    pacing = payload.get("pacing_json")
    if isinstance(pacing, str):
        try:
            payload["pacing_json"] = json.loads(pacing)
        except json.JSONDecodeError:
            payload["pacing_json"] = None
    if "run_headless" in payload:
        raw_headless = payload["run_headless"]
        payload["run_headless"] = bool(raw_headless) if raw_headless is not None else None
    if "is_running" in payload:
        payload["is_running"] = bool(payload.get("is_running"))
    return _normalize_time_fields(payload)


def update_schedule_sync(**fields) -> dict[str, Any]:
    allowed = {
        "enabled",
        "cron",
        "item_limit",
        "collect_ratings",
        "account_state_file",
        "account_strategy",
        "is_running",
        "pacing_json",
        "last_run_summary",
        "last_run_saved",
        "last_run_ok",
        "last_run_at",
        "run_headless",
    }
    updates = {key: fields[key] for key in allowed if key in fields}
    if not updates:
        return get_schedule_sync()
    if "pacing_json" in updates and updates["pacing_json"] is not None:
        updates["pacing_json"] = json.dumps(updates["pacing_json"], ensure_ascii=False)
    set_clause = ", ".join(f"{key} = ?" for key in updates)
    params = list(updates.values())
    bootstrap_storage()
    with db_connection() as conn:
        conn.execute(
            f"UPDATE seller_subscription_schedule SET {set_clause} WHERE id = 1",
            params,
        )
        conn.commit()
    return get_schedule_sync()


def touch_subscription_captured_sync(seller_user_id: str, nickname: str | None = None) -> None:
    bootstrap_storage()
    with db_connection() as conn:
        conn.execute(
            """
            UPDATE seller_subscriptions
            SET last_captured_at = ?, nickname = COALESCE(?, nickname)
            WHERE seller_user_id = ?
            """,
            (shanghai_now_iso(), nickname, seller_user_id),
        )
        conn.commit()


async def list_latest_item_metrics(
    task_name: str,
    seller_user_id: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(
        list_latest_item_metrics_sync,
        task_name,
        seller_user_id,
        limit,
    )


async def list_latest_item_metrics_paginated(
    task_name: str,
    seller_user_id: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "snapshot_time",
    sort_order: str = "desc",
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(
        lambda: list_latest_item_metrics_paginated_sync(
            task_name,
            seller_user_id=seller_user_id,
            search=search,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    )


async def count_latest_item_metrics(
    task_name: str,
    seller_user_id: str | None = None,
    search: str | None = None,
) -> int:
    return await asyncio.to_thread(
        lambda: count_latest_item_metrics_sync(
            task_name,
            seller_user_id=seller_user_id,
            search=search,
        )
    )


async def list_subscriptions() -> list[dict[str, Any]]:
    return await asyncio.to_thread(list_subscriptions_sync)


async def get_subscription(subscription_id: int) -> dict[str, Any] | None:
    return await asyncio.to_thread(get_subscription_sync, subscription_id)


async def get_subscription_by_user(seller_user_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(get_subscription_by_user_sync, seller_user_id)


async def get_latest_profile(task_name: str, seller_user_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(get_latest_profile_sync, task_name, seller_user_id)


async def add_subscription(**kwargs) -> dict[str, Any]:
    return await asyncio.to_thread(lambda: add_subscription_sync(**kwargs))


async def update_subscription(subscription_id: int, **fields) -> dict[str, Any] | None:
    return await asyncio.to_thread(lambda: update_subscription_sync(subscription_id, **fields))


async def delete_subscription(subscription_id: int) -> bool:
    return await asyncio.to_thread(delete_subscription_sync, subscription_id)


async def list_enabled_seller_ids() -> list[str]:
    return await asyncio.to_thread(list_enabled_seller_ids_sync)


async def get_schedule() -> dict[str, Any]:
    return await asyncio.to_thread(get_schedule_sync)


async def update_schedule(**fields) -> dict[str, Any]:
    return await asyncio.to_thread(lambda: update_schedule_sync(**fields))


async def touch_subscription_captured(seller_user_id: str, nickname: str | None = None) -> None:
    await asyncio.to_thread(touch_subscription_captured_sync, seller_user_id, nickname)


async def set_subscription_running(is_running: bool) -> dict[str, Any]:
    return await update_schedule(is_running=is_running)


def record_subscription_run_sync(
    summary: str,
    *,
    saved: int = 0,
    ok: bool = False,
) -> dict[str, Any]:
    return update_schedule_sync(
        is_running=False,
        last_run_summary=summary,
        last_run_saved=saved,
        last_run_ok=ok,
        last_run_at=shanghai_now_iso(),
    )


async def record_subscription_run(summary: str, *, saved: int = 0, ok: bool = False) -> dict[str, Any]:
    return await asyncio.to_thread(record_subscription_run_sync, summary, saved=saved, ok=ok)

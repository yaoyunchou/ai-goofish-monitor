"""订阅卖家画像与商品指标存储。"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from src.infrastructure.persistence.db_connection import db_connection
from src.infrastructure.persistence.sql_dialect import json_text
from src.infrastructure.persistence.storage_bootstrap import bootstrap_storage
from src.services.price_history_service import parse_price_value


def save_seller_profile_sync(task_name: str, seller_user_id: str, profile: dict) -> None:
    bootstrap_storage()
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO seller_profiles (
                task_name, seller_user_id, nickname, shop_level, praise_ratio,
                followers, item_count, rating_count, profile_json, captured_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_name,
                seller_user_id,
                profile.get("卖家昵称"),
                profile.get("鱼小铺等级"),
                profile.get("好评率"),
                profile.get("粉丝数"),
                profile.get("卖家在售/已售商品数"),
                profile.get("卖家收到的评价总数"),
                json_text(profile),
                datetime.now().isoformat(),
            ),
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
                datetime.now().isoformat(),
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


def list_latest_item_metrics_sync(
    task_name: str,
    seller_user_id: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    bootstrap_storage()
    conditions = ["task_name = ?"]
    params: list[Any] = [task_name]
    if seller_user_id:
        conditions.append("seller_user_id = ?")
        params.append(seller_user_id)
    sql = f"""
        SELECT DISTINCT ON (item_id)
            task_name, seller_user_id, item_id, title, price, item_status,
            want_count, view_count, snapshot_time
        FROM seller_item_metrics
        WHERE {' AND '.join(conditions)}
        ORDER BY item_id, snapshot_time DESC
        LIMIT ?
    """
    params.append(limit)
    with db_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    metrics = [dict(row) for row in rows]
    metrics.sort(key=lambda row: row.get("snapshot_time") or "", reverse=True)
    return metrics


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
    return [dict(row) for row in rows]


def get_subscription_sync(subscription_id: int) -> dict[str, Any] | None:
    bootstrap_storage()
    with db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM seller_subscriptions WHERE id = ?",
            (subscription_id,),
        ).fetchone()
    return dict(row) if row else None


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
    return payload


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
            (datetime.now().isoformat(), nickname, seller_user_id),
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


async def list_subscriptions() -> list[dict[str, Any]]:
    return await asyncio.to_thread(list_subscriptions_sync)


async def get_subscription(subscription_id: int) -> dict[str, Any] | None:
    return await asyncio.to_thread(get_subscription_sync, subscription_id)


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
        last_run_at=datetime.now().isoformat(),
    )


async def record_subscription_run(summary: str, *, saved: int = 0, ok: bool = False) -> dict[str, Any]:
    return await asyncio.to_thread(record_subscription_run_sync, summary, saved=saved, ok=ok)

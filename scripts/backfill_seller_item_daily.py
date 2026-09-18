"""将历史 seller_item_metrics / result_items / item_detail_api_raw 回填到日级表。

用法:
  python scripts/backfill_seller_item_daily.py
  python scripts/backfill_seller_item_daily.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.infrastructure.persistence.db_connection import db_connection, ensure_incremental_schema
from src.infrastructure.persistence.sql_dialect import json_text, parse_json_field
from src.infrastructure.persistence.storage_bootstrap import bootstrap_storage
from src.infrastructure.persistence.storage_names import build_result_filename

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _to_shanghai_day(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat") and not isinstance(value, str):
        # date / datetime
        if hasattr(value, "hour"):
            dt = value
            if getattr(dt, "tzinfo", None) is None:
                dt = dt.replace(tzinfo=SHANGHAI)
            else:
                dt = dt.astimezone(SHANGHAI)
            return dt.date().isoformat()
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text[:10] if len(text) >= 10 else None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SHANGHAI)
    else:
        dt = dt.astimezone(SHANGHAI)
    return dt.date().isoformat()


def backfill(*, dry_run: bool = False) -> dict[str, int]:
    bootstrap_storage()
    stats = {
        "items_upserted": 0,
        "daily_inserted": 0,
        "daily_skipped": 0,
        "profiles_updated": 0,
    }

    with db_connection() as conn:
        ensure_incremental_schema(conn)

        # 1) 静态主表：每商品取最新 metrics 行
        latest_items = conn.execute(
            """
            SELECT DISTINCT ON (task_name, seller_user_id, item_id)
                task_name, seller_user_id, item_id, title, price, item_status, snapshot_time
            FROM seller_item_metrics
            WHERE item_id IS NOT NULL AND item_id <> ''
            ORDER BY task_name, seller_user_id, item_id, snapshot_time DESC
            """
        ).fetchall()

        for row in latest_items:
            captured = row.get("snapshot_time")
            captured_iso = (
                captured.isoformat() if hasattr(captured, "isoformat") else str(captured or datetime.now(tz=SHANGHAI).isoformat())
            )
            if dry_run:
                stats["items_upserted"] += 1
                continue
            conn.execute(
                """
                INSERT INTO seller_subscription_items (
                    task_name, seller_user_id, item_id, title, price, item_status,
                    item_link, main_image, first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (task_name, seller_user_id, item_id) DO UPDATE SET
                    title = COALESCE(EXCLUDED.title, seller_subscription_items.title),
                    price = COALESCE(EXCLUDED.price, seller_subscription_items.price),
                    item_status = COALESCE(EXCLUDED.item_status, seller_subscription_items.item_status),
                    last_seen_at = GREATEST(seller_subscription_items.last_seen_at, EXCLUDED.last_seen_at)
                """,
                (
                    row["task_name"],
                    row["seller_user_id"],
                    row["item_id"],
                    row.get("title"),
                    row.get("price"),
                    row.get("item_status"),
                    None,
                    None,
                    captured_iso,
                    captured_iso,
                ),
            )
            stats["items_upserted"] += 1

        # 2) 日指标：每天取最后一条 metrics
        daily_rows = conn.execute(
            """
            SELECT DISTINCT ON (
                task_name, seller_user_id, item_id,
                (snapshot_time AT TIME ZONE 'Asia/Shanghai')::date
            )
                task_name, seller_user_id, item_id, title, price, item_status,
                want_count, view_count, snapshot_time,
                (snapshot_time AT TIME ZONE 'Asia/Shanghai')::date AS snapshot_day
            FROM seller_item_metrics
            WHERE item_id IS NOT NULL AND item_id <> ''
            ORDER BY
                task_name, seller_user_id, item_id,
                (snapshot_time AT TIME ZONE 'Asia/Shanghai')::date,
                snapshot_time DESC
            """
        ).fetchall()

        for row in daily_rows:
            day = row.get("snapshot_day")
            day_str = day.isoformat() if hasattr(day, "isoformat") else _to_shanghai_day(row.get("snapshot_time"))
            if not day_str:
                stats["daily_skipped"] += 1
                continue

            existing = conn.execute(
                """
                SELECT id FROM seller_item_daily_metrics
                WHERE task_name = ? AND seller_user_id = ? AND item_id = ? AND snapshot_day = ?
                """,
                (row["task_name"], row["seller_user_id"], row["item_id"], day_str),
            ).fetchone()
            if existing:
                stats["daily_skipped"] += 1
                continue

            # 拼 raw：result_items + item_detail_api_raw（同日尽量匹配）
            result_filename = build_result_filename(row["task_name"])
            result_row = conn.execute(
                """
                SELECT raw_json, crawl_time FROM result_items
                WHERE item_id = ? AND result_filename = ?
                ORDER BY id DESC LIMIT 1
                """,
                (row["item_id"], result_filename),
            ).fetchone()
            crawl_record = parse_json_field(result_row["raw_json"], default={}) if result_row else {
                "商品信息": {
                    "商品ID": row["item_id"],
                    "商品标题": row.get("title"),
                    "当前售价": row.get("price"),
                    "商品状态": row.get("item_status"),
                },
                "任务名称": row["task_name"],
                "任务类型": "seller_subscription",
                "爬取时间": str(row.get("snapshot_time") or ""),
            }

            detail_row = conn.execute(
                """
                SELECT raw_json FROM item_detail_api_raw
                WHERE item_id = ? AND task_name = ?
                  AND (captured_at AT TIME ZONE 'Asia/Shanghai')::date = CAST(? AS date)
                ORDER BY captured_at DESC LIMIT 1
                """,
                (row["item_id"], row["task_name"], day_str),
            ).fetchone()
            if not detail_row:
                detail_row = conn.execute(
                    """
                    SELECT raw_json FROM item_detail_api_raw
                    WHERE item_id = ? AND task_name = ?
                    ORDER BY captured_at DESC LIMIT 1
                    """,
                    (row["item_id"], row["task_name"]),
                ).fetchone()
            detail_api_raw = parse_json_field(detail_row["raw_json"], default=None) if detail_row else None

            captured = row.get("snapshot_time")
            captured_iso = (
                captured.isoformat()
                if hasattr(captured, "isoformat")
                else str(captured or datetime.now(tz=SHANGHAI).isoformat())
            )
            raw_payload = {"crawl_record": crawl_record, "detail_api_raw": detail_api_raw}

            if dry_run:
                stats["daily_inserted"] += 1
                continue

            raw_inserted = conn.execute(
                """
                INSERT INTO crawl_raw_records (created_at, updated_at, raw_json)
                VALUES (?, ?, ?)
                RETURNING id
                """,
                (captured_iso, captured_iso, json_text(raw_payload)),
            ).fetchone()
            raw_id = int(raw_inserted["id"])
            conn.execute(
                """
                INSERT INTO seller_item_daily_metrics (
                    task_name, seller_user_id, item_id, snapshot_day,
                    want_count, view_count, captured_at, raw_record_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (task_name, seller_user_id, item_id, snapshot_day) DO NOTHING
                """,
                (
                    row["task_name"],
                    row["seller_user_id"],
                    row["item_id"],
                    day_str,
                    row.get("want_count"),
                    row.get("view_count"),
                    captured_iso,
                    raw_id,
                ),
            )
            stats["daily_inserted"] += 1

        # 3) seller_profiles.profile_day：每个 (task, seller, day) 只给最新一条打标
        if dry_run:
            pending = conn.execute(
                """
                SELECT COUNT(*) AS total FROM (
                    SELECT DISTINCT ON (
                        task_name, seller_user_id,
                        (captured_at AT TIME ZONE 'Asia/Shanghai')::date
                    ) id
                    FROM seller_profiles
                    WHERE profile_day IS NULL
                    ORDER BY
                        task_name, seller_user_id,
                        (captured_at AT TIME ZONE 'Asia/Shanghai')::date,
                        captured_at DESC, id DESC
                ) t
                """
            ).fetchone()
            stats["profiles_updated"] = int(pending["total"]) if pending else 0
        else:
            cursor = conn.execute(
                """
                WITH ranked AS (
                    SELECT
                        id,
                        (captured_at AT TIME ZONE 'Asia/Shanghai')::date AS day,
                        ROW_NUMBER() OVER (
                            PARTITION BY
                                task_name,
                                seller_user_id,
                                (captured_at AT TIME ZONE 'Asia/Shanghai')::date
                            ORDER BY captured_at DESC, id DESC
                        ) AS rn
                    FROM seller_profiles
                    WHERE profile_day IS NULL
                )
                UPDATE seller_profiles p
                SET profile_day = ranked.day
                FROM ranked
                WHERE p.id = ranked.id AND ranked.rn = 1
                """
            )
            stats["profiles_updated"] = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0

        if not dry_run:
            conn.commit()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill seller item daily schema")
    parser.add_argument("--dry-run", action="store_true", help="只统计不写入")
    args = parser.parse_args()
    result = backfill(dry_run=args.dry_run)
    prefix = "[dry-run] " if args.dry_run else ""
    print(f"{prefix}backfill done: {result}")


if __name__ == "__main__":
    main()

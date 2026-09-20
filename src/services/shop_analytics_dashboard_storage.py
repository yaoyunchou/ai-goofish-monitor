"""店铺分析看板：订阅日指标只读 SQL 聚合。"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Any, Mapping

from src.domain.seller_subscription import SELLER_SUBSCRIPTION_TASK_NAME
from src.domain.shop_analytics_dashboard import (
    DASHBOARD_PERIODS,
    DASHBOARD_TIMEZONE,
    DashboardCards,
    DashboardHotItem,
    DashboardShopRow,
    DashboardTrendPoint,
    ShopAnalyticsDashboard,
    ShopAnalyticsPeriod,
)
from src.infrastructure.persistence.db_connection import db_connection
from src.infrastructure.persistence.storage_bootstrap import bootstrap_storage
from src.services.seller_subscription_storage import get_schedule_sync
from src.time_utils import shanghai_today, to_shanghai_iso

TASK_NAME = SELLER_SUBSCRIPTION_TASK_NAME

# 看板聚合忽略已退订卖家的残留日指标。
SQL_SUBSCRIBED_SELLER = """
EXISTS (
  SELECT 1 FROM seller_subscriptions sub
  WHERE sub.seller_user_id = seller_item_daily_metrics.seller_user_id
)
"""
SQL_SUBSCRIBED_SELLER_M = """
EXISTS (
  SELECT 1 FROM seller_subscriptions sub
  WHERE sub.seller_user_id = m.seller_user_id
)
"""

SQL_HAS_DATA = f"""
SELECT 1
FROM seller_item_daily_metrics
WHERE task_name = ?
  AND {SQL_SUBSCRIBED_SELLER}
LIMIT 1
"""

SQL_ENABLED_SHOPS = """
SELECT COUNT(*) AS enabled_shop_count
FROM seller_subscriptions
WHERE enabled IS TRUE
"""

SQL_ANCHOR_DAY = f"""
SELECT MAX(snapshot_day) AS anchor_day
FROM seller_item_daily_metrics
WHERE task_name = ?
  AND snapshot_day BETWEEN ? AND ?
  AND {SQL_SUBSCRIBED_SELLER}
"""

SQL_CARDS = f"""
SELECT
  COUNT(DISTINCT item_id) AS item_count,
  COUNT(DISTINCT seller_user_id) AS shops_with_data,
  COALESCE(SUM(want_count), 0) AS want_sum,
  COALESCE(SUM(view_count), 0) AS view_sum,
  MAX(captured_at) AS last_captured_at
FROM seller_item_daily_metrics
WHERE task_name = ?
  AND snapshot_day = ?
  AND {SQL_SUBSCRIBED_SELLER}
"""

SQL_RANGE_DISTINCT = f"""
SELECT
  COUNT(DISTINCT item_id) AS item_count,
  COUNT(DISTINCT seller_user_id) AS shops_with_data
FROM seller_item_daily_metrics
WHERE task_name = ?
  AND snapshot_day BETWEEN ? AND ?
  AND {SQL_SUBSCRIBED_SELLER}
"""

SQL_TREND = f"""
WITH days AS (
  SELECT generate_series(?::date, ?::date, interval '1 day')::date AS snapshot_day
),
agg AS (
  SELECT
    snapshot_day,
    SUM(want_count) AS want_sum,
    SUM(view_count) AS view_sum
  FROM seller_item_daily_metrics
  WHERE task_name = ?
    AND snapshot_day BETWEEN ? AND ?
    AND {SQL_SUBSCRIBED_SELLER}
  GROUP BY snapshot_day
)
SELECT
  d.snapshot_day,
  a.want_sum,
  a.view_sum
FROM days d
LEFT JOIN agg a ON a.snapshot_day = d.snapshot_day
ORDER BY d.snapshot_day
"""

SQL_SHOP_RANKING = f"""
WITH shop_agg AS (
  SELECT
    seller_user_id,
    COUNT(DISTINCT item_id) AS item_count,
    COALESCE(SUM(want_count), 0) AS want_sum,
    COALESCE(SUM(view_count), 0) AS view_sum
  FROM seller_item_daily_metrics
  WHERE task_name = ?
    AND snapshot_day = ?
    AND {SQL_SUBSCRIBED_SELLER}
  GROUP BY seller_user_id
)
SELECT
  a.seller_user_id,
  a.item_count,
  a.want_sum,
  a.view_sum,
  COALESCE(p.nickname, s.nickname, a.seller_user_id) AS shop_name,
  COALESCE(s.enabled, FALSE) AS enabled
FROM shop_agg a
INNER JOIN seller_subscriptions s ON s.seller_user_id = a.seller_user_id
LEFT JOIN LATERAL (
  SELECT nickname
  FROM seller_profiles
  WHERE task_name = ?
    AND seller_user_id = a.seller_user_id
  ORDER BY captured_at DESC
  LIMIT 1
) p ON TRUE
ORDER BY a.view_sum DESC NULLS LAST
"""

SQL_HOT_ITEMS = f"""
SELECT
  m.item_id,
  m.seller_user_id,
  m.want_count,
  m.view_count,
  i.title,
  COALESCE(p.nickname, s.nickname, m.seller_user_id) AS shop_name
FROM seller_item_daily_metrics m
LEFT JOIN seller_subscription_items i
  ON i.task_name = m.task_name
 AND i.seller_user_id = m.seller_user_id
 AND i.item_id = m.item_id
INNER JOIN seller_subscriptions s ON s.seller_user_id = m.seller_user_id
LEFT JOIN LATERAL (
  SELECT nickname
  FROM seller_profiles
  WHERE task_name = ?
    AND seller_user_id = m.seller_user_id
  ORDER BY captured_at DESC
  LIMIT 1
) p ON TRUE
WHERE m.task_name = ?
  AND m.snapshot_day = ?
  AND {SQL_SUBSCRIBED_SELLER_M}
ORDER BY m.view_count DESC NULLS LAST
LIMIT 10
"""


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    return date.fromisoformat(text[:10])


def _as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    return int(value)


def _as_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _as_bool(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes"}
    return bool(value)


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _scopes(period: ShopAnalyticsPeriod) -> tuple[str, str]:
    if period == "7d":
        return "range", "latest_day_in_range"
    return "anchor_day", "anchor_day"


def _empty_cards(period: ShopAnalyticsPeriod, enabled_shop_count: int) -> DashboardCards:
    item_count_scope, want_view_scope = _scopes(period)
    return {
        "enabled_shop_count": enabled_shop_count,
        "shops_with_data": 0,
        "item_count": 0,
        "want_sum": 0,
        "view_sum": 0,
        "item_count_scope": item_count_scope,  # type: ignore[typeddict-item]
        "want_view_scope": want_view_scope,  # type: ignore[typeddict-item]
    }


def _build_trend(range_start: date, range_end: date, rows: list[Mapping[str, Any]] | None) -> list[DashboardTrendPoint]:
    by_day: dict[date, Mapping[str, Any]] = {}
    for row in rows or []:
        day = _as_date(row.get("snapshot_day") or row.get("date"))
        if day is None:
            continue
        by_day[day] = row
    points: list[DashboardTrendPoint] = []
    cursor = range_start
    while cursor <= range_end:
        row = by_day.get(cursor)
        if row is None:
            want = None
            view = None
        else:
            want = _as_int_or_none(row.get("want_sum", row.get("want")))
            view = _as_int_or_none(row.get("view_sum", row.get("view")))
        points.append({"date": cursor.isoformat(), "want": want, "view": view})
        cursor += timedelta(days=1)
    return points


def _map_shops(rows: list[Mapping[str, Any]] | None) -> list[DashboardShopRow]:
    shops: list[DashboardShopRow] = []
    for row in rows or []:
        seller_user_id = _as_str(row.get("seller_user_id"))
        if not seller_user_id:
            continue
        shop_name = _as_str(row.get("shop_name")).strip() or seller_user_id
        shops.append(
            {
                "seller_user_id": seller_user_id,
                "shop_name": shop_name,
                "item_count": _as_int(row.get("item_count")),
                "want_sum": _as_int(row.get("want_sum")),
                "view_sum": _as_int(row.get("view_sum")),
                "enabled": _as_bool(row.get("enabled")),
            }
        )
    return shops


def _map_hot_items(rows: list[Mapping[str, Any]] | None) -> list[DashboardHotItem]:
    items: list[DashboardHotItem] = []
    for row in rows or []:
        item_id = _as_str(row.get("item_id"))
        if not item_id:
            continue
        seller_user_id = _as_str(row.get("seller_user_id"))
        shop_name = _as_str(row.get("shop_name")).strip() or seller_user_id or item_id
        title = row.get("title")
        items.append(
            {
                "item_id": item_id,
                "title": None if title is None or str(title).strip() == "" else str(title),
                "seller_user_id": seller_user_id,
                "shop_name": shop_name,
                "want_count": _as_int_or_none(row.get("want_count")),
                "view_count": _as_int_or_none(row.get("view_count")),
            }
        )
    return items


def get_subscription_dashboard_sync(
    period: ShopAnalyticsPeriod = "today",
    today: date | None = None,
) -> ShopAnalyticsDashboard:
    if period not in DASHBOARD_PERIODS:
        raise ValueError(f"unsupported period: {period}")

    bootstrap_storage()
    today_date = today or shanghai_today()
    range_end = today_date
    range_start = today_date - timedelta(days=6)
    item_count_scope, want_view_scope = _scopes(period)

    with db_connection() as conn:
        has_row = conn.execute(SQL_HAS_DATA, (TASK_NAME,)).fetchone()
        has_data = has_row is not None

        enabled_row = conn.execute(SQL_ENABLED_SHOPS).fetchone() or {}
        enabled_shop_count = _as_int(enabled_row.get("enabled_shop_count"))

        anchor: date | None
        if period == "today":
            anchor = today_date
        elif has_data:
            anchor_row = conn.execute(
                SQL_ANCHOR_DAY,
                (TASK_NAME, range_start.isoformat(), range_end.isoformat()),
            ).fetchone() or {}
            anchor = _as_date(anchor_row.get("anchor_day"))
        else:
            anchor = None

        cards = _empty_cards(period, enabled_shop_count)
        last_captured_at: Any = None
        shops: list[DashboardShopRow] = []
        hot_items: list[DashboardHotItem] = []
        trend_rows: list[Mapping[str, Any]] = []

        if has_data:
            if anchor is not None:
                card_row = conn.execute(
                    SQL_CARDS,
                    (TASK_NAME, anchor.isoformat()),
                ).fetchone() or {}
                cards["item_count"] = _as_int(card_row.get("item_count"))
                cards["shops_with_data"] = _as_int(card_row.get("shops_with_data"))
                cards["want_sum"] = _as_int(card_row.get("want_sum"))
                cards["view_sum"] = _as_int(card_row.get("view_sum"))
                last_captured_at = card_row.get("last_captured_at")

            if period == "7d":
                range_row = conn.execute(
                    SQL_RANGE_DISTINCT,
                    (TASK_NAME, range_start.isoformat(), range_end.isoformat()),
                ).fetchone() or {}
                cards["item_count"] = _as_int(range_row.get("item_count"))
                cards["shops_with_data"] = _as_int(range_row.get("shops_with_data"))
                if anchor is None:
                    cards["want_sum"] = None
                    cards["view_sum"] = None

            trend_rows = list(
                conn.execute(
                    SQL_TREND,
                    (
                        range_start.isoformat(),
                        range_end.isoformat(),
                        TASK_NAME,
                        range_start.isoformat(),
                        range_end.isoformat(),
                    ),
                ).fetchall()
                or []
            )

            if anchor is not None:
                shops = _map_shops(
                    list(
                        conn.execute(
                            SQL_SHOP_RANKING,
                            (TASK_NAME, anchor.isoformat(), TASK_NAME),
                        ).fetchall()
                        or []
                    )
                )
                hot_items = _map_hot_items(
                    list(
                        conn.execute(
                            SQL_HOT_ITEMS,
                            (TASK_NAME, TASK_NAME, anchor.isoformat()),
                        ).fetchall()
                        or []
                    )
                )

    schedule = get_schedule_sync()
    trend = _build_trend(range_start, range_end, trend_rows)
    cards["enabled_shop_count"] = enabled_shop_count
    cards["item_count_scope"] = item_count_scope  # type: ignore[typeddict-item]
    cards["want_view_scope"] = want_view_scope  # type: ignore[typeddict-item]

    return {
        "period": period,
        "timezone": DASHBOARD_TIMEZONE,
        "today": today_date.isoformat(),
        "range_start": range_start.isoformat(),
        "range_end": range_end.isoformat(),
        "anchor_day": None if anchor is None else anchor.isoformat(),
        "has_data": has_data,
        "freshness": {
            "last_captured_at": to_shanghai_iso(last_captured_at),
            "last_run_at": to_shanghai_iso(schedule.get("last_run_at")),
        },
        "cards": cards,
        "trend": trend,
        "shops": shops,
        "hot_items": hot_items,
    }


async def get_subscription_dashboard(
    period: ShopAnalyticsPeriod = "today",
    today: date | None = None,
) -> ShopAnalyticsDashboard:
    return await asyncio.to_thread(get_subscription_dashboard_sync, period, today)

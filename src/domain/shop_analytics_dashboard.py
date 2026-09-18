"""店铺分析看板（卖家订阅日指标）契约。"""
from __future__ import annotations

from typing import Literal, TypedDict

ShopAnalyticsPeriod = Literal["today", "7d"]
DASHBOARD_PERIODS: tuple[ShopAnalyticsPeriod, ...] = ("today", "7d")
DASHBOARD_TIMEZONE = "Asia/Shanghai"

ItemCountScope = Literal["anchor_day", "range"]
WantViewScope = Literal["anchor_day", "latest_day_in_range"]


class DashboardFreshness(TypedDict):
    last_captured_at: str | None
    last_run_at: str | None


class DashboardCards(TypedDict):
    enabled_shop_count: int
    shops_with_data: int
    item_count: int
    want_sum: int | None
    view_sum: int | None
    item_count_scope: ItemCountScope
    want_view_scope: WantViewScope


class DashboardTrendPoint(TypedDict):
    date: str
    want: int | None
    view: int | None


class DashboardShopRow(TypedDict):
    seller_user_id: str
    shop_name: str
    item_count: int
    want_sum: int
    view_sum: int
    enabled: bool


class DashboardHotItem(TypedDict):
    item_id: str
    title: str | None
    seller_user_id: str
    shop_name: str
    want_count: int | None
    view_count: int | None


class ShopAnalyticsDashboard(TypedDict):
    period: ShopAnalyticsPeriod
    timezone: str
    today: str
    range_start: str
    range_end: str
    anchor_day: str | None
    has_data: bool
    freshness: DashboardFreshness
    cards: DashboardCards
    trend: list[DashboardTrendPoint]
    shops: list[DashboardShopRow]
    hot_items: list[DashboardHotItem]

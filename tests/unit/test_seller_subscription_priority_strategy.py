"""卖家订阅采集三阶段策略：独立可辨识用例。

阶段零：对齐全部订阅卖家商品列表（只拉主页，不点详情），店间短预热。
从未采过的店铺（last_captured_at 为空）在列表对齐和详情阶段都排最前。
阶段一：所有店「今日无日指标」的商品先采。
阶段二：今日已有指标的商品后更新。
"""
from __future__ import annotations

import asyncio
import importlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

from src.domain.seller_subscription_pacing import (
    SubscriptionPacing,
    SubscriptionPacingConfig,
)
from src.seller_subscription_scraper import (
    SellerScrapePlan,
    _build_work_queue,
    _never_captured_seller_ids,
    _order_seller_ids_for_alignment,
)

_MODULE = "src.seller_subscription_scraper"


def _load_scraper_module():
    if _MODULE in sys.modules:
        return importlib.reload(sys.modules[_MODULE])
    return importlib.import_module(_MODULE)


def _item(item_id: str, title: str = "") -> dict:
    return {
        "商品ID": item_id,
        "商品标题": title or item_id,
        "商品状态": "在售",
        "商品链接": f"https://www.goofish.com/item?id={item_id}",
    }


def _profile(user_id: str, item_ids: list[str], nick: str = "") -> dict:
    return {
        "卖家ID": user_id,
        "卖家昵称": nick or user_id,
        "卖家发布的商品列表": [_item(item_id) for item_id in item_ids],
    }


def _ok_detail() -> dict:
    return {
        "ok": True,
        "“想要”人数": 1,
        "浏览量": 2,
        "商品图片列表": [],
        "商品描述": "",
    }


def _pacing_mock() -> MagicMock:
    pacing = MagicMock()
    pacing.log_plan = MagicMock()
    pacing.before_seller = AsyncMock()
    pacing.before_list_alignment = AsyncMock()
    pacing.before_profile = AsyncMock()
    pacing.before_detail = AsyncMock()
    pacing.after_detail = AsyncMock()
    return pacing


def _fake_launch(_task_config):
    async def _launch(_task_config):
        browser = AsyncMock()
        browser.close = AsyncMock()
        playwright = AsyncMock()
        playwright.stop = AsyncMock()
        return playwright, browser, AsyncMock(), "state/test.json"

    return AsyncMock(side_effect=_launch)


# ---------------------------------------------------------------------------
# 阶段零：列表对齐顺序与短预热
# ---------------------------------------------------------------------------


def test_alignment_orders_never_captured_sellers_first():
    ordered = _order_seller_ids_for_alignment(
        ["old-b", "new-b", "old-a", "new-a"],
        {"new-b", "new-a"},
    )
    assert ordered[:2] == ["new-a", "new-b"]
    assert ordered[2:] == ["old-a", "old-b"]


def test_alignment_keeps_captured_sellers_after_never_captured():
    ordered = _order_seller_ids_for_alignment(
        ["s3", "s1", "s2"],
        {"s2"},
    )
    assert ordered[0] == "s2"
    assert ordered[1:] == ["s1", "s3"]


def test_never_captured_seller_ids_from_empty_last_captured_at():
    rows = [
        {"seller_user_id": "new-shop", "last_captured_at": None},
        {"seller_user_id": "old-shop", "last_captured_at": "2026-09-17T10:00:00+08:00"},
        {"seller_user_id": "also-new", "last_captured_at": ""},
        {"seller_user_id": "  ", "last_captured_at": None},
    ]
    with patch(
        "src.seller_subscription_scraper.list_subscriptions_sync",
        return_value=rows,
    ):
        assert _never_captured_seller_ids() == {"new-shop", "also-new"}


def test_never_captured_seller_ids_empty_when_storage_fails():
    with patch(
        "src.seller_subscription_scraper.list_subscriptions_sync",
        side_effect=RuntimeError("db down"),
    ):
        assert _never_captured_seller_ids() == set()


def test_before_list_alignment_uses_short_warmup_not_seller_cooldown():
    sleeps: list[tuple[float, float]] = []

    async def fake_sleep(lo, hi):
        sleeps.append((lo, hi))

    pacing = SubscriptionPacing(SubscriptionPacingConfig.from_mapping(None))
    with patch("src.domain.seller_subscription_pacing.random_sleep", new=fake_sleep):
        asyncio.run(pacing.before_list_alignment(0))
        asyncio.run(pacing.before_list_alignment(1))
        asyncio.run(pacing.before_seller(1))

    assert sleeps[0] == (
        pacing.config.profile_warmup_min,
        pacing.config.profile_warmup_max,
    )
    assert sleeps[0][1] <= 6.0
    assert sleeps[1] == (
        pacing.config.seller_cooldown_min,
        pacing.config.seller_cooldown_max,
    )
    assert sleeps[1][0] >= 120.0


def test_phase0_does_not_call_before_seller_long_cooldown():
    """阶段零店间只用 before_list_alignment，禁止套用 before_seller 长冷却。"""
    mod = _load_scraper_module()
    profiles = {
        "11111111111": _profile("11111111111", ["old-item"]),
        "22222222222": _profile("22222222222", ["new-item"]),
    }
    events: list[str] = []

    async def fake_profile(_context, user_id, **_kwargs):
        events.append(f"profile:{user_id}")
        return profiles[user_id]

    async def fake_detail(_context, link):
        events.append(f"detail:{link.split('id=')[-1]}")
        return _ok_detail()

    pacing = _pacing_mock()

    async def record_alignment(seller_index):
        events.append(f"align:{seller_index}")

    async def record_before_seller(_seller_index):
        events.append("before_seller")

    pacing.before_list_alignment = AsyncMock(side_effect=record_alignment)
    pacing.before_seller = AsyncMock(side_effect=record_before_seller)

    with (
        patch.object(mod.SubscriptionPacing, "from_task_config", return_value=pacing),
        patch.object(mod, "list_item_ids_with_daily_snapshot_sync", return_value=set()),
        patch.object(mod, "_never_captured_seller_ids", return_value={"22222222222"}),
        patch.object(mod, "launch_task_browser", _fake_launch({})),
        patch.object(mod, "scrape_user_profile", new=AsyncMock(side_effect=fake_profile)),
        patch.object(mod, "fetch_item_detail", new=AsyncMock(side_effect=fake_detail)),
        patch.object(mod, "save_seller_profile", new=AsyncMock()),
        patch.object(mod, "upsert_seller_item_daily_snapshot", new=AsyncMock()),
        patch.object(mod, "touch_subscription_captured", new=AsyncMock()),
    ):
        asyncio.run(
            mod.scrape_seller_subscription(
                {
                    "task_name": "seller_subscriptions",
                    "seller_user_ids": ["11111111111", "22222222222"],
                    "item_limit": 10,
                }
            )
        )

    first_detail = next(i for i, e in enumerate(events) if e.startswith("detail:"))
    phase0 = events[:first_detail]
    assert [e for e in phase0 if e.startswith("profile:")] == [
        "profile:22222222222",
        "profile:11111111111",
    ]
    assert "before_seller" not in phase0
    assert "align:0" in phase0 and "align:1" in phase0
    assert pacing.before_list_alignment.await_count == 2


def test_phase0_scrapes_all_profiles_before_any_item_detail():
    mod = _load_scraper_module()
    profiles = {
        "11111111111": _profile("11111111111", ["a-item"]),
        "22222222222": _profile("22222222222", ["b-item"]),
        "33333333333": _profile("33333333333", ["c-item"]),
    }
    events: list[str] = []

    async def fake_profile(_context, user_id, **_kwargs):
        events.append(f"profile:{user_id}")
        return profiles[user_id]

    async def fake_detail(_context, link):
        events.append("detail")
        return _ok_detail()

    pacing = _pacing_mock()
    with (
        patch.object(mod.SubscriptionPacing, "from_task_config", return_value=pacing),
        patch.object(mod, "list_item_ids_with_daily_snapshot_sync", return_value=set()),
        patch.object(mod, "_never_captured_seller_ids", return_value=set()),
        patch.object(mod, "launch_task_browser", _fake_launch({})),
        patch.object(mod, "scrape_user_profile", new=AsyncMock(side_effect=fake_profile)),
        patch.object(mod, "fetch_item_detail", new=AsyncMock(side_effect=fake_detail)),
        patch.object(mod, "save_seller_profile", new=AsyncMock()),
        patch.object(mod, "upsert_seller_item_daily_snapshot", new=AsyncMock()),
        patch.object(mod, "touch_subscription_captured", new=AsyncMock()),
    ):
        asyncio.run(
            mod.scrape_seller_subscription(
                {
                    "task_name": "seller_subscriptions",
                    "seller_user_ids": ["11111111111", "22222222222", "33333333333"],
                    "item_limit": 10,
                }
            )
        )

    kinds = ["profile" if e.startswith("profile:") else e for e in events]
    last_profile = max(i for i, k in enumerate(kinds) if k == "profile")
    first_detail = kinds.index("detail")
    assert last_profile < first_detail
    assert kinds.count("profile") == 3


# ---------------------------------------------------------------------------
# 从未采过的店铺：对齐 + 详情都优先于「今日缺采更多」的老店
# ---------------------------------------------------------------------------


def test_never_captured_shop_goes_before_old_shop_with_more_missing():
    old = SellerScrapePlan(
        user_id="old-shop",
        profile={},
        missing_items=[_item("old-m1"), _item("old-m2"), _item("old-m3")],
        covered_items=[_item("old-c1")],
        never_captured=False,
    )
    new = SellerScrapePlan(
        user_id="new-shop",
        profile={},
        missing_items=[_item("new-m1")],
        covered_items=[_item("new-c1")],
        never_captured=True,
    )
    phase_missing, phase_updates = _build_work_queue([old, new])

    missing_ids = [item["商品ID"] for _, item in phase_missing]
    update_ids = [item["商品ID"] for _, item in phase_updates]
    assert missing_ids[0] == "new-m1"
    assert set(missing_ids[1:]) == {"old-m1", "old-m2", "old-m3"}
    assert update_ids[0] == "new-c1"
    assert update_ids[1] == "old-c1"


def test_prioritize_sellers_never_captured_beats_higher_missing_count():
    plans = [
        {"user_id": "old-seller", "missing_count": 80, "never_captured": False},
        {"user_id": "new-seller", "missing_count": 1, "never_captured": True},
        {"user_id": "also-old", "missing_count": 40, "never_captured": False},
    ]
    ordered = SubscriptionPacing.prioritize_sellers_by_missing(plans)
    assert ordered[0]["user_id"] == "new-seller"
    assert [p["user_id"] for p in ordered[1:]] == ["old-seller", "also-old"]


def test_alignment_and_detail_both_put_never_captured_shop_first():
    """列表对齐与详情队列都把从未采过的店排在缺采更多的老店前面。"""
    never_ids = {"22222222222"}
    aligned = _order_seller_ids_for_alignment(
        ["11111111111", "22222222222"],
        never_ids,
    )
    assert aligned[0] == "22222222222"

    phase_missing, _phase_updates = _build_work_queue(
        [
            SellerScrapePlan(
                user_id="11111111111",
                profile={},
                missing_items=[_item("old-1"), _item("old-2")],
                never_captured=False,
            ),
            SellerScrapePlan(
                user_id="22222222222",
                profile={},
                missing_items=[_item("new-1")],
                never_captured=True,
            ),
        ]
    )
    assert phase_missing[0][0].user_id == "22222222222"
    assert phase_missing[0][1]["商品ID"] == "new-1"


# ---------------------------------------------------------------------------
# 阶段一 / 阶段二：今日无指标先于已有指标
# ---------------------------------------------------------------------------


def test_items_without_today_snapshot_before_covered():
    items = [
        {"商品ID": "covered-a"},
        {"商品ID": "missing-b"},
        {"商品ID": "covered-c"},
        {"商品ID": "missing-d"},
    ]
    ordered = SubscriptionPacing.prioritize_missing_today(items, {"covered-a", "covered-c"})
    missing_ids = {item["商品ID"] for item in ordered[:2]}
    covered_ids = {item["商品ID"] for item in ordered[2:]}
    assert missing_ids == {"missing-b", "missing-d"}
    assert covered_ids == {"covered-a", "covered-c"}


def test_build_work_queue_phase1_all_missing_then_phase2_updates():
    """全局两阶段：所有店未采集先于任何店的今日已有指标。"""
    shop_a = SellerScrapePlan(
        user_id="shop-a",
        profile={},
        missing_items=[_item("a-missing")],
        covered_items=[_item("a-covered")],
        never_captured=False,
    )
    shop_b = SellerScrapePlan(
        user_id="shop-b",
        profile={},
        missing_items=[_item("b-missing")],
        covered_items=[_item("b-covered")],
        never_captured=False,
    )
    phase_missing, phase_updates = _build_work_queue([shop_a, shop_b])

    missing_ids = [item["商品ID"] for _, item in phase_missing]
    update_ids = [item["商品ID"] for _, item in phase_updates]
    assert set(missing_ids) == {"a-missing", "b-missing"}
    assert set(update_ids) == {"a-covered", "b-covered"}
    assert "a-covered" not in missing_ids
    assert "b-covered" not in missing_ids


def test_scrape_phase1_missing_across_shops_before_any_phase2_update():
    mod = _load_scraper_module()
    profiles = {
        "11111111111": _profile("11111111111", ["old-covered", "old-missing"]),
        "22222222222": _profile("22222222222", ["new-covered", "new-missing"]),
    }
    call_order: list[str] = []

    async def fake_profile(_context, user_id, **_kwargs):
        return profiles[user_id]

    async def fake_detail(_context, link):
        call_order.append(link.split("id=")[-1])
        return _ok_detail()

    def fake_covered_ids(**kwargs):
        seller = kwargs.get("seller_user_id")
        if seller == "11111111111":
            return {"old-covered"}
        if seller == "22222222222":
            return {"new-covered"}
        return set()

    pacing = _pacing_mock()
    with (
        patch.object(mod.SubscriptionPacing, "from_task_config", return_value=pacing),
        patch.object(mod, "list_item_ids_with_daily_snapshot_sync", side_effect=fake_covered_ids),
        patch.object(mod, "_never_captured_seller_ids", return_value={"22222222222"}),
        patch.object(mod, "launch_task_browser", _fake_launch({})),
        patch.object(mod, "scrape_user_profile", new=AsyncMock(side_effect=fake_profile)),
        patch.object(mod, "fetch_item_detail", new=AsyncMock(side_effect=fake_detail)),
        patch.object(mod, "save_seller_profile", new=AsyncMock()),
        patch.object(mod, "upsert_seller_item_daily_snapshot", new=AsyncMock()),
        patch.object(mod, "touch_subscription_captured", new=AsyncMock()),
    ):
        asyncio.run(
            mod.scrape_seller_subscription(
                {
                    "task_name": "seller_subscriptions",
                    "seller_user_ids": ["11111111111", "22222222222"],
                    "item_limit": 10,
                }
            )
        )

    assert set(call_order[:2]) == {"new-missing", "old-missing"}
    assert call_order[0] == "new-missing"
    assert set(call_order[2:]) == {"new-covered", "old-covered"}
    assert call_order[2] == "new-covered"

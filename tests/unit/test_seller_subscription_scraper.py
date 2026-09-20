"""卖家订阅爬虫 mock 集成测试：入库过滤与空配置。"""
import asyncio
import importlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

_MODULE = "src.seller_subscription_scraper"


def _load_scraper_module():
    """CLI 集成测会 pop 本模块，需在用例内重新 import。"""
    if _MODULE in sys.modules:
        return importlib.reload(sys.modules[_MODULE])
    return importlib.import_module(_MODULE)


def test_scrape_seller_subscription_without_sellers_returns_zero(offline_db):
    mod = _load_scraper_module()
    saved = asyncio.run(
        mod.scrape_seller_subscription(
            {"task_name": "seller_subscriptions", "seller_user_ids": []},
        )
    )
    assert saved == 0


def test_scrape_seller_subscription_skips_items_without_want_and_view():
    mod = _load_scraper_module()
    profile = {
        "卖家ID": "2221197154547",
        "卖家昵称": "测试卖家",
        "卖家发布的商品列表": [
            {
                "商品ID": "good-1",
                "商品标题": "有效商品",
                "商品状态": "在售",
                "商品链接": "https://www.goofish.com/item?id=good-1",
            },
            {
                "商品ID": "bad-1",
                "商品标题": "缺指标",
                "商品状态": "在售",
                "商品链接": "https://www.goofish.com/item?id=bad-1",
            },
        ],
    }

    async def fake_profile(*_args, **_kwargs):
        return profile

    async def fake_detail(_context, link):
        if "good-1" in link:
            return {
                "ok": True,
                "“想要”人数": 3,
                "浏览量": 10,
                "商品图片列表": [],
                "商品描述": "",
            }
        return {
            "ok": True,
            "“想要”人数": "NaN",
            "浏览量": 10,
            "商品图片列表": [],
            "商品描述": "",
        }

    saved_metrics = []

    async def fake_save_snapshot(**kwargs):
        saved_metrics.append(kwargs["item"]["商品ID"])

    async def fake_launch(_task_config):
        browser = AsyncMock()
        browser.close = AsyncMock()
        playwright = AsyncMock()
        playwright.stop = AsyncMock()
        return playwright, browser, AsyncMock(), "state/test.json"

    pacing = MagicMock()
    pacing.log_plan = MagicMock()
    pacing.before_seller = AsyncMock()
    pacing.before_list_alignment = AsyncMock()
    pacing.before_profile = AsyncMock()
    pacing.before_detail = AsyncMock()
    pacing.after_detail = AsyncMock()
    with (
        patch.object(
            mod,
            "list_item_ids_with_daily_snapshot_sync",
            return_value=set(),
        ),
        patch.object(mod, "load_muted_item_ids_sync", return_value=set()),
        patch.object(mod.SubscriptionPacing, "from_task_config", return_value=pacing),
        patch.object(mod, "launch_task_browser", new=AsyncMock(side_effect=fake_launch)),
        patch.object(mod, "scrape_user_profile", new=AsyncMock(side_effect=fake_profile)),
        patch.object(mod, "fetch_item_detail", new=AsyncMock(side_effect=fake_detail)),
        patch.object(mod, "save_seller_profile", new=AsyncMock()),
        patch.object(
            mod, "upsert_seller_item_daily_snapshot", new=AsyncMock(side_effect=fake_save_snapshot)
        ),
        patch.object(mod, "touch_subscription_captured", new=AsyncMock()),
        patch.object(mod, "_never_captured_seller_ids", return_value=set()),
    ):
        saved = asyncio.run(
            mod.scrape_seller_subscription(
                {
                    "task_name": "seller_subscriptions",
                    "seller_user_ids": ["2221197154547"],
                    "item_limit": 10,
                }
            )
        )

    assert saved == 1
    assert saved_metrics == ["good-1"]


def test_scrape_prioritizes_items_without_today_snapshot():
    mod = _load_scraper_module()
    profile = {
        "卖家ID": "2221197154547",
        "卖家昵称": "测试卖家",
        "卖家发布的商品列表": [
            {
                "商品ID": "item-1",
                "商品标题": "已有今日",
                "商品状态": "在售",
                "商品链接": "https://www.goofish.com/item?id=item-1",
            },
            {
                "商品ID": "item-2",
                "商品标题": "今日未采集",
                "商品状态": "在售",
                "商品链接": "https://www.goofish.com/item?id=item-2",
            },
        ],
    }
    call_order: list[str] = []

    async def fake_profile(*_args, **_kwargs):
        return profile

    async def fake_detail(_context, link):
        call_order.append(link)
        return {
            "ok": True,
            "“想要”人数": 1,
            "浏览量": 2,
            "商品图片列表": [],
            "商品描述": "",
        }

    async def fake_save_snapshot(**_kwargs):
        return None

    async def fake_launch(_task_config):
        browser = AsyncMock()
        browser.close = AsyncMock()
        playwright = AsyncMock()
        playwright.stop = AsyncMock()
        return playwright, browser, AsyncMock(), "state/test.json"

    pacing = MagicMock()
    pacing.log_plan = MagicMock()
    pacing.before_seller = AsyncMock()
    pacing.before_list_alignment = AsyncMock()
    pacing.before_profile = AsyncMock()
    pacing.before_detail = AsyncMock()
    pacing.after_detail = AsyncMock()

    def fake_prioritize(items, covered):
        missing = [it for it in items if it["商品ID"] not in covered]
        covered_items = [it for it in items if it["商品ID"] in covered]
        return missing + covered_items

    with (
        patch.object(mod.SubscriptionPacing, "from_task_config", return_value=pacing),
        patch.object(mod.SubscriptionPacing, "prioritize_missing_today", side_effect=fake_prioritize),
        patch.object(
            mod,
            "list_item_ids_with_daily_snapshot_sync",
            return_value={"item-1"},
        ),
        patch.object(mod, "load_muted_item_ids_sync", return_value=set()),
        patch.object(mod, "launch_task_browser", new=AsyncMock(side_effect=fake_launch)),
        patch.object(mod, "scrape_user_profile", new=AsyncMock(side_effect=fake_profile)),
        patch.object(mod, "fetch_item_detail", new=AsyncMock(side_effect=fake_detail)),
        patch.object(mod, "save_seller_profile", new=AsyncMock()),
        patch.object(mod, "upsert_seller_item_daily_snapshot", new=AsyncMock(side_effect=fake_save_snapshot)),
        patch.object(mod, "touch_subscription_captured", new=AsyncMock()),
        patch.object(mod, "_never_captured_seller_ids", return_value=set()),
    ):
        asyncio.run(
            mod.scrape_seller_subscription(
                {
                    "task_name": "seller_subscriptions",
                    "seller_user_ids": ["2221197154547"],
                    "item_limit": 10,
                }
            )
        )

    assert call_order[0].endswith("item-2")
    assert call_order[1].endswith("item-1")


def test_scrape_runs_new_seller_missing_before_old_seller_updates():
    mod = _load_scraper_module()
    profiles = {
        "11111111111": {
            "卖家ID": "11111111111",
            "卖家昵称": "老店",
            "卖家发布的商品列表": [
                {
                    "商品ID": "old-covered",
                    "商品标题": "老店已采集",
                    "商品状态": "在售",
                    "商品链接": "https://www.goofish.com/item?id=old-covered",
                },
            ],
        },
        "22222222222": {
            "卖家ID": "22222222222",
            "卖家昵称": "新店",
            "卖家发布的商品列表": [
                {
                    "商品ID": "new-missing",
                    "商品标题": "新店未采集",
                    "商品状态": "在售",
                    "商品链接": "https://www.goofish.com/item?id=new-missing",
                },
            ],
        },
    }
    call_order: list[str] = []

    async def fake_profile(_context, user_id, **_kwargs):
        return profiles[user_id]

    async def fake_detail(_context, link):
        call_order.append(link)
        return {
            "ok": True,
            "“想要”人数": 1,
            "浏览量": 2,
            "商品图片列表": [],
            "商品描述": "",
        }

    async def fake_launch(_task_config):
        browser = AsyncMock()
        browser.close = AsyncMock()
        playwright = AsyncMock()
        playwright.stop = AsyncMock()
        return playwright, browser, AsyncMock(), "state/test.json"

    pacing = MagicMock()
    pacing.log_plan = MagicMock()
    pacing.before_seller = AsyncMock()
    pacing.before_list_alignment = AsyncMock()
    pacing.before_profile = AsyncMock()
    pacing.before_detail = AsyncMock()
    pacing.after_detail = AsyncMock()

    def fake_covered_ids(**kwargs):
        if kwargs.get("seller_user_id") == "11111111111":
            return {"old-covered"}
        return set()

    with (
        patch.object(mod.SubscriptionPacing, "from_task_config", return_value=pacing),
        patch.object(mod, "list_item_ids_with_daily_snapshot_sync", side_effect=fake_covered_ids),
        patch.object(mod, "load_muted_item_ids_sync", return_value=set()),
        patch.object(mod, "launch_task_browser", new=AsyncMock(side_effect=fake_launch)),
        patch.object(mod, "scrape_user_profile", new=AsyncMock(side_effect=fake_profile)),
        patch.object(mod, "fetch_item_detail", new=AsyncMock(side_effect=fake_detail)),
        patch.object(mod, "save_seller_profile", new=AsyncMock()),
        patch.object(mod, "upsert_seller_item_daily_snapshot", new=AsyncMock()),
        patch.object(mod, "touch_subscription_captured", new=AsyncMock()),
        patch.object(mod, "_never_captured_seller_ids", return_value=set()),
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

    assert call_order[0].endswith("new-missing")
    assert call_order[1].endswith("old-covered")
    assert pacing.before_seller.await_count == 1


def test_scrape_never_captured_shop_before_old_shop_even_if_fewer_missing():
    mod = _load_scraper_module()
    profiles = {
        "11111111111": {
            "卖家ID": "11111111111",
            "卖家发布的商品列表": [
                {
                    "商品ID": "old-missing-1",
                    "商品标题": "老店缺今天",
                    "商品状态": "在售",
                    "商品链接": "https://www.goofish.com/item?id=old-missing-1",
                },
                {
                    "商品ID": "old-missing-2",
                    "商品标题": "老店也缺今天",
                    "商品状态": "在售",
                    "商品链接": "https://www.goofish.com/item?id=old-missing-2",
                },
            ],
        },
        "22222222222": {
            "卖家ID": "22222222222",
            "卖家发布的商品列表": [
                {
                    "商品ID": "new-missing",
                    "商品标题": "新店唯一",
                    "商品状态": "在售",
                    "商品链接": "https://www.goofish.com/item?id=new-missing",
                },
            ],
        },
    }
    call_order: list[str] = []

    async def fake_profile(_context, user_id, **_kwargs):
        return profiles[user_id]

    async def fake_detail(_context, link):
        call_order.append(link)
        return {"ok": True, "“想要”人数": 1, "浏览量": 2, "商品图片列表": [], "商品描述": ""}

    async def fake_launch(_task_config):
        browser = AsyncMock()
        browser.close = AsyncMock()
        playwright = AsyncMock()
        playwright.stop = AsyncMock()
        return playwright, browser, AsyncMock(), "state/test.json"

    pacing = MagicMock()
    pacing.log_plan = MagicMock()
    pacing.before_seller = AsyncMock()
    pacing.before_list_alignment = AsyncMock()
    pacing.before_profile = AsyncMock()
    pacing.before_detail = AsyncMock()
    pacing.after_detail = AsyncMock()

    with (
        patch.object(mod.SubscriptionPacing, "from_task_config", return_value=pacing),
        patch.object(mod, "list_item_ids_with_daily_snapshot_sync", return_value=set()),
        patch.object(mod, "load_muted_item_ids_sync", return_value=set()),
        patch.object(mod, "_never_captured_seller_ids", return_value={"22222222222"}),
        patch.object(mod, "launch_task_browser", new=AsyncMock(side_effect=fake_launch)),
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

    assert call_order[0].endswith("new-missing")
    assert {link.split("id=")[-1] for link in call_order[1:]} == {"old-missing-1", "old-missing-2"}


def test_scrape_registered_without_enabled_subscriptions(monkeypatch):
    mod = _load_scraper_module()
    recorded = []

    async def fake_record(summary, saved=0, ok=False):
        recorded.append((summary, saved, ok))

    async def fake_config():
        return None

    import src.services.seller_subscription_service as subscription_service

    monkeypatch.setattr(subscription_service, "build_scrape_task_config", fake_config)
    monkeypatch.setattr(mod, "record_subscription_run", fake_record)

    saved = asyncio.run(mod.scrape_registered_seller_subscriptions())
    assert saved == 0
    assert recorded
    assert recorded[-1][2] is False
    assert "没有启用的卖家订阅" in recorded[-1][0]


def test_scrape_reports_whole_skipped_seller_in_summary(capsys):
    """整店被跳过（主页 0 条在售）时，结尾汇总必须显式列出该店。

    回归背景：曾出现「2 个卖家只跑 1 个」，但结尾只打印
    `扫描 N → 详情 N → 入库 N → 跳过 0`，被 continue 掉的店铺不进任何分母，
    导致看起来「一切正常」，极易误判。此处锁定新的 [店铺汇总] 输出。
    """
    mod = _load_scraper_module()

    profiles = {
        # A 店正常，有 1 条在售
        "11111111111": {
            "卖家ID": "11111111111",
            "卖家昵称": "正常店",
            "卖家发布的商品列表": [
                {
                    "商品ID": "a-1",
                    "商品标题": "正常商品",
                    "商品状态": "在售",
                    "商品链接": "https://www.goofish.com/item?id=a-1",
                },
            ],
        },
        # B 店主页解析出 0 条 → 整店跳过
        "22222222222": {
            "卖家ID": "22222222222",
            "卖家昵称": "空店",
            "卖家发布的商品列表": [],
        },
    }

    async def fake_profile(_context, user_id, **_kwargs):
        return profiles[str(user_id)]

    async def fake_detail(_context, _link):
        return {
            "ok": True,
            "“想要”人数": 5,
            "浏览量": 20,
            "商品图片列表": [],
            "商品描述": "",
        }

    async def fake_launch(_task_config):
        browser = AsyncMock()
        browser.close = AsyncMock()
        playwright = AsyncMock()
        playwright.stop = AsyncMock()
        return playwright, browser, AsyncMock(), "state/test.json"

    pacing = MagicMock()
    pacing.log_plan = MagicMock()
    pacing.before_seller = AsyncMock()
    pacing.before_list_alignment = AsyncMock()
    pacing.before_profile = AsyncMock()
    pacing.before_detail = AsyncMock()
    pacing.after_detail = AsyncMock()
    with (
        patch.object(mod, "list_item_ids_with_daily_snapshot_sync", return_value=set()),
        patch.object(mod, "load_muted_item_ids_sync", return_value=set()),
        patch.object(mod.SubscriptionPacing, "from_task_config", return_value=pacing),
        patch.object(mod, "launch_task_browser", new=AsyncMock(side_effect=fake_launch)),
        patch.object(mod, "scrape_user_profile", new=AsyncMock(side_effect=fake_profile)),
        patch.object(mod, "fetch_item_detail", new=AsyncMock(side_effect=fake_detail)),
        patch.object(mod, "save_seller_profile", new=AsyncMock()),
        patch.object(mod, "upsert_seller_item_daily_snapshot", new=AsyncMock()),
        patch.object(mod, "touch_subscription_captured", new=AsyncMock()),
        patch.object(mod, "_never_captured_seller_ids", return_value=set()),
    ):
        saved = asyncio.run(
            mod.scrape_seller_subscription(
                {
                    "task_name": "seller_subscriptions",
                    "seller_user_ids": ["11111111111", "22222222222"],
                    "item_limit": 10,
                }
            )
        )

    out = capsys.readouterr().out

    # A 店照常入库；B 店 0 条
    assert saved == 1
    # 新增：整店跳过必须被显式汇总，而不是只在中间打一行日志
    assert "[店铺汇总]" in out, "缺少整店跳过的汇总行"
    assert "订阅 2 家" in out
    assert "有商品入库 1 家" in out
    assert "整店跳过 1 家" in out
    assert "跳过店铺 22222222222" in out
    assert "主页无在售商品" in out
    # 被跳过的店不应出现在「有商品入库」里
    assert "跳过店铺 11111111111" not in out


def test_still_subscribed_true_when_subscription_exists():
    mod = _load_scraper_module()
    with patch.object(mod, "get_subscription_by_user_sync", return_value={"id": 1}):
        assert mod._still_subscribed("2221197154547") is True


def test_still_subscribed_false_when_subscription_deleted():
    """订阅被删除 → 采集途中必须识别出来，否则会把刚清干净的商品又写回去。"""
    mod = _load_scraper_module()
    with patch.object(mod, "get_subscription_by_user_sync", return_value=None):
        assert mod._still_subscribed("2221197154547") is False


def test_still_subscribed_fails_open_on_db_error(capsys):
    """DB 读不到时按「仍订阅」处理：这只是保护，不能中断整轮采集。"""
    mod = _load_scraper_module()
    with patch.object(mod, "get_subscription_by_user_sync", side_effect=RuntimeError("db down")):
        assert mod._still_subscribed("2221197154547") is True
    assert "校验卖家" in capsys.readouterr().out

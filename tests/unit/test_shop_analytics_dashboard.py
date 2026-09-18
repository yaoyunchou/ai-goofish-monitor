"""店铺分析看板：订阅日指标聚合口径。"""
from datetime import date, datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from src.services.shop_analytics_dashboard_storage import (
    SQL_CARDS,
    SQL_HOT_ITEMS,
    SQL_RANGE_DISTINCT,
    SQL_SHOP_RANKING,
    SQL_TREND,
    get_subscription_dashboard_sync,
)


def _cursor(fetchone=None, fetchall=None):
    cur = MagicMock()
    cur.fetchone.return_value = fetchone
    cur.fetchall.return_value = fetchall or []
    return cur


def _classify(sql: str) -> str:
    text = " ".join(sql.split()).lower()
    if "generate_series" in text:
        return "trend"
    if "shop_agg" in text:
        return "shops"
    if "limit 10" in text:
        return "hot"
    if "enabled_shop_count" in text:
        return "enabled"
    if "max(snapshot_day)" in text:
        return "anchor"
    if "last_captured_at" in text:
        return "cards"
    if "count(distinct item_id)" in text and "between" in text:
        return "range"
    if "select 1" in text:
        return "exists"
    raise AssertionError(f"unexpected sql: {sql}")


def _dispatch(sql: str, params=None, *, mapping: dict):
    kind = _classify(sql)
    if kind not in mapping:
        raise AssertionError(f"no mock for {kind}: {sql} params={params}")
    payload = mapping[kind]
    if isinstance(payload, list):
        return _cursor(fetchall=payload)
    return _cursor(fetchone=payload)


def _run(mapping: dict, *, period="today", today=date(2026, 9, 17), last_run_at="2026-09-17T17:38:17+08:00"):
    conn = MagicMock()
    conn.execute.side_effect = lambda sql, params=None: _dispatch(sql, params, mapping=mapping)
    cm = MagicMock()
    cm.__enter__.return_value = conn
    cm.__exit__.return_value = False
    with (
        patch("src.services.shop_analytics_dashboard_storage.bootstrap_storage"),
        patch("src.services.shop_analytics_dashboard_storage.db_connection", return_value=cm),
        patch(
            "src.services.shop_analytics_dashboard_storage.get_schedule_sync",
            return_value={"last_run_at": last_run_at},
        ),
        patch(
            "src.services.shop_analytics_dashboard_storage.shanghai_today",
            return_value=today,
        ),
    ):
        result = get_subscription_dashboard_sync(period, today=today)
    return result, conn


def test_empty_metrics_returns_seven_null_trend_points():
    mapping = {
        "exists": None,
        "enabled": {"enabled_shop_count": 2},
    }
    result, _conn = _run(mapping)

    assert result["has_data"] is False
    assert len(result["trend"]) == 7
    assert result["trend"][0]["date"] == "2026-09-11"
    assert result["trend"][-1]["date"] == "2026-09-17"
    for point in result["trend"]:
        assert point["want"] is None
        assert point["view"] is None
        assert point["want"] != 0
        assert point["view"] != 0
    assert result["shops"] == []
    assert result["hot_items"] == []
    assert result["cards"]["item_count"] == 0
    assert result["cards"]["want_sum"] == 0
    assert result["anchor_day"] == "2026-09-17"
    assert result["freshness"]["last_run_at"].startswith("2026-09-17T17:38:17")


def test_two_day_metrics_keeps_hollow_days_as_null_not_zero():
    mapping = {
        "exists": {"ok": 1},
        "enabled": {"enabled_shop_count": 2},
        "cards": {
            "item_count": 181,
            "shops_with_data": 2,
            "want_sum": 8344,
            "view_sum": 65071,
            "last_captured_at": datetime(2026, 9, 17, 17, 38, 17, tzinfo=ZoneInfo("Asia/Shanghai")),
        },
        "trend": [
            {"snapshot_day": date(2026, 9, 16), "want_sum": 100, "view_sum": 2000},
            {"snapshot_day": date(2026, 9, 17), "want_sum": 8344, "view_sum": 65071},
        ],
        "shops": [
            {
                "seller_user_id": "a",
                "item_count": 80,
                "want_sum": 8175,
                "view_sum": 63308,
                "shop_name": "笑笑书馆",
                "enabled": True,
            },
            {
                "seller_user_id": "b",
                "item_count": 101,
                "want_sum": 169,
                "view_sum": 1763,
                "shop_name": "妮吧啦啦",
                "enabled": True,
            },
        ],
        "hot": [
            {
                "item_id": "1",
                "seller_user_id": "a",
                "want_count": 10,
                "view_count": 100,
                "title": "书",
                "shop_name": "笑笑书馆",
            }
        ],
    }
    result, conn = _run(mapping, period="today")

    assert result["has_data"] is True
    assert result["cards"]["item_count"] == 181
    assert result["cards"]["want_sum"] == 8344
    assert result["cards"]["view_sum"] == 65071
    assert len(result["trend"]) == 7
    solid = [point for point in result["trend"] if point["want"] is not None or point["view"] is not None]
    hollow = [point for point in result["trend"] if point["want"] is None and point["view"] is None]
    assert len(solid) == 2
    assert len(hollow) == 5
    for point in hollow:
        assert point["want"] is None
        assert point["view"] is None
        assert point["want"] != 0
        assert point["view"] != 0
    assert result["shops"][0]["shop_name"] == "笑笑书馆"
    assert result["shops"][0]["view_sum"] > result["shops"][1]["view_sum"]
    sqls = "\n".join(call.args[0] for call in conn.execute.call_args_list)
    assert "GROUP BY snapshot_day" in sqls


def test_period_7d_does_not_sum_want_view_across_days():
    mapping = {
        "exists": {"ok": 1},
        "enabled": {"enabled_shop_count": 2},
        "anchor": {"anchor_day": date(2026, 9, 17)},
        "cards": {
            "item_count": 181,
            "shops_with_data": 2,
            "want_sum": 50,
            "view_sum": 500,
            "last_captured_at": datetime(2026, 9, 17, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        },
        "range": {"item_count": 185, "shops_with_data": 2},
        "trend": [
            {"snapshot_day": date(2026, 9, 16), "want_sum": 100, "view_sum": 1000},
            {"snapshot_day": date(2026, 9, 17), "want_sum": 50, "view_sum": 500},
        ],
        "shops": [],
        "hot": [],
    }
    result, conn = _run(mapping, period="7d")

    assert result["period"] == "7d"
    assert result["anchor_day"] == "2026-09-17"
    assert result["cards"]["want_sum"] == 50
    assert result["cards"]["view_sum"] == 500
    assert result["cards"]["want_sum"] != 150
    assert result["cards"]["view_sum"] != 1500
    assert result["cards"]["item_count"] == 185
    assert result["cards"]["item_count_scope"] == "range"
    assert result["cards"]["want_view_scope"] == "latest_day_in_range"
    sqls = "\n".join(call.args[0] for call in conn.execute.call_args_list)
    assert "BETWEEN" in sqls
    card_sql = next(call.args[0] for call in conn.execute.call_args_list if "last_captured_at" in call.args[0])
    assert "BETWEEN" not in card_sql


def test_dashboard_sql_uses_group_by_not_select_star():
    mapping = {
        "exists": {"ok": 1},
        "enabled": {"enabled_shop_count": 1},
        "anchor": {"anchor_day": date(2026, 9, 17)},
        "cards": {
            "item_count": 1,
            "shops_with_data": 1,
            "want_sum": 1,
            "view_sum": 1,
            "last_captured_at": None,
        },
        "range": {"item_count": 1, "shops_with_data": 1},
        "trend": [],
        "shops": [],
        "hot": [],
    }
    _result, conn = _run(mapping, period="7d")
    sqls = "\n".join(call.args[0] for call in conn.execute.call_args_list)
    assert "GROUP BY snapshot_day" in sqls
    assert "COUNT(DISTINCT" in sqls
    assert "SUM(want_count)" in sqls
    compact = " ".join(sqls.split())
    assert "SELECT * FROM seller_item_daily_metrics" not in compact
    assert "COALESCE(a.want_sum" not in sqls
    for fragment in (SQL_TREND, SQL_CARDS, SQL_RANGE_DISTINCT, SQL_SHOP_RANKING, SQL_HOT_ITEMS):
        assert "SELECT *" not in " ".join(fragment.split())


def test_shop_name_falls_back_to_seller_user_id():
    mapping = {
        "exists": {"ok": 1},
        "enabled": {"enabled_shop_count": 2},
        "cards": {
            "item_count": 2,
            "shops_with_data": 2,
            "want_sum": 3,
            "view_sum": 4,
            "last_captured_at": None,
        },
        "trend": [],
        "shops": [
            {
                "seller_user_id": "uid-profile",
                "item_count": 1,
                "want_sum": 1,
                "view_sum": 8,
                "shop_name": "画像店名",
                "enabled": True,
            },
            {
                "seller_user_id": "uid-bare",
                "item_count": 1,
                "want_sum": 2,
                "view_sum": 3,
                "shop_name": None,
                "enabled": False,
            },
        ],
        "hot": [
            {
                "item_id": "i1",
                "seller_user_id": "uid-bare",
                "want_count": 2,
                "view_count": 3,
                "title": None,
                "shop_name": "",
            }
        ],
    }
    result, conn = _run(mapping)
    names = {row["seller_user_id"]: row["shop_name"] for row in result["shops"]}
    assert names["uid-profile"] == "画像店名"
    assert names["uid-bare"] == "uid-bare"
    assert result["shops"][1]["enabled"] is False
    assert result["hot_items"][0]["shop_name"] == "uid-bare"
    sqls = "\n".join(call.args[0] for call in conn.execute.call_args_list)
    assert "COALESCE(p.nickname, s.nickname" in sqls


def test_empty_metrics_period_7d_still_seven_null_trend_points():
    mapping = {
        "exists": None,
        "enabled": {"enabled_shop_count": 0},
    }
    result, _conn = _run(mapping, period="7d")

    assert result["has_data"] is False
    assert result["anchor_day"] is None
    assert len(result["trend"]) == 7
    for point in result["trend"]:
        assert point["want"] is None
        assert point["view"] is None
        assert point["want"] != 0
        assert point["view"] != 0
    assert result["cards"]["want_sum"] == 0
    assert result["cards"]["view_sum"] == 0
    assert result["cards"]["item_count"] == 0


def test_period_7d_empty_range_want_view_are_null_not_zero():
    mapping = {
        "exists": {"ok": 1},
        "enabled": {"enabled_shop_count": 2},
        "anchor": {"anchor_day": None},
        "range": {"item_count": 0, "shops_with_data": 0},
        "trend": [],
    }
    result, conn = _run(mapping, period="7d")

    assert result["has_data"] is True
    assert result["anchor_day"] is None
    assert result["cards"]["want_sum"] is None
    assert result["cards"]["view_sum"] is None
    assert result["cards"]["want_sum"] != 0
    assert result["cards"]["view_sum"] != 0
    assert result["cards"]["item_count"] == 0
    assert result["cards"]["want_view_scope"] == "latest_day_in_range"
    assert len(result["trend"]) == 7
    assert all(point["want"] is None and point["view"] is None for point in result["trend"])
    sqls = "\n".join(call.args[0] for call in conn.execute.call_args_list)
    assert "generate_series" in sqls.lower()


def test_invalid_period_raises_before_sql():
    try:
        get_subscription_dashboard_sync("30d", today=date(2026, 9, 17))
    except ValueError as exc:
        assert "unsupported period" in str(exc)
        return
    raise AssertionError("expected ValueError for period=30d")


def test_enabled_shop_count_can_differ_from_shops_with_data():
    mapping = {
        "exists": {"ok": 1},
        "enabled": {"enabled_shop_count": 5},
        "cards": {
            "item_count": 181,
            "shops_with_data": 2,
            "want_sum": 10,
            "view_sum": 20,
            "last_captured_at": None,
        },
        "trend": [],
        "shops": [],
        "hot": [],
    }
    result, _conn = _run(mapping)
    assert result["cards"]["enabled_shop_count"] == 5
    assert result["cards"]["shops_with_data"] == 2
    assert result["cards"]["enabled_shop_count"] != result["cards"]["shops_with_data"]

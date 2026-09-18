"""卖家订阅日级存储单元测试。"""
from datetime import date, datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from src.services.seller_item_daily_storage import (
    _row_to_legacy_metric,
    shanghai_today,
    upsert_seller_item_daily_snapshot_sync,
)


def test_shanghai_today_uses_asia_shanghai():
    fixed = datetime(2026, 9, 16, 23, 30, tzinfo=ZoneInfo("UTC"))
    # UTC 23:30 = Asia/Shanghai 次日 07:30
    assert shanghai_today(fixed) == date(2026, 9, 17)


def test_row_to_legacy_metric_maps_snapshot_time():
    row = {
        "task_name": "seller_subscriptions",
        "seller_user_id": "u1",
        "item_id": "i1",
        "title": "商品",
        "price": 9.9,
        "item_status": "在售",
        "want_count": 1,
        "view_count": 2,
        "captured_at": datetime(2026, 9, 17, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        "snapshot_day": date(2026, 9, 17),
        "raw_record_id": 5,
    }
    mapped = _row_to_legacy_metric(row)
    assert mapped["snapshot_time"].startswith("2026-09-17")
    assert mapped["snapshot_day"] == "2026-09-17"
    assert mapped["want_count"] == 1
    assert mapped["title"] == "商品"


def test_upsert_same_day_updates_existing_raw():
    """同日第二次采集应 UPDATE raw，不新增 raw 行。"""
    conn = MagicMock()
    existing = {"id": 10, "raw_record_id": 7}
    conn.execute.side_effect = [
        MagicMock(),  # upsert items
        MagicMock(fetchone=MagicMock(return_value=existing)),  # select existing
        MagicMock(),  # update raw
        MagicMock(),  # update metrics
    ]

    cm = MagicMock()
    cm.__enter__.return_value = conn
    cm.__exit__.return_value = False

    with (
        patch("src.services.seller_item_daily_storage.bootstrap_storage"),
        patch("src.services.seller_item_daily_storage.db_connection", return_value=cm),
        patch(
            "src.services.seller_item_daily_storage.shanghai_today",
            return_value=date(2026, 9, 17),
        ),
        patch(
            "src.services.seller_item_daily_storage.shanghai_now_iso",
            return_value="2026-09-17T16:00:00+08:00",
        ),
    ):
        result = upsert_seller_item_daily_snapshot_sync(
            task_name="seller_subscriptions",
            seller_user_id="u1",
            item={
                "商品ID": "item-1",
                "商品标题": "标题",
                "当前售价": "10",
                "商品状态": "在售",
                "商品链接": "https://www.goofish.com/item?id=item-1",
                "_want_count": 5,
                "_view_count": 9,
            },
            crawl_record={"商品信息": {"商品ID": "item-1"}},
            detail_api_raw={"api": "mtop.taobao.idle.pc.detail", "data": {}},
        )

    assert result["raw_record_id"] == 7
    assert result["metrics_id"] == 10
    assert result["snapshot_day"] == "2026-09-17"
    assert conn.execute.call_count == 4
    update_raw_sql = conn.execute.call_args_list[2][0][0]
    assert "UPDATE crawl_raw_records" in update_raw_sql
    conn.commit.assert_called_once()


def test_upsert_new_day_inserts_raw_and_metrics():
    conn = MagicMock()
    conn.execute.side_effect = [
        MagicMock(),  # upsert items
        MagicMock(fetchone=MagicMock(return_value=None)),  # no existing
        MagicMock(fetchone=MagicMock(return_value={"id": 99})),  # insert raw
        MagicMock(fetchone=MagicMock(return_value={"id": 88})),  # insert metrics
    ]
    cm = MagicMock()
    cm.__enter__.return_value = conn
    cm.__exit__.return_value = False

    with (
        patch("src.services.seller_item_daily_storage.bootstrap_storage"),
        patch("src.services.seller_item_daily_storage.db_connection", return_value=cm),
        patch(
            "src.services.seller_item_daily_storage.shanghai_today",
            return_value=date(2026, 9, 17),
        ),
        patch(
            "src.services.seller_item_daily_storage.shanghai_now_iso",
            return_value="2026-09-17T08:00:00+08:00",
        ),
    ):
        result = upsert_seller_item_daily_snapshot_sync(
            task_name="seller_subscriptions",
            seller_user_id="u1",
            item={"商品ID": "item-2", "_want_count": 1, "_view_count": 2},
            crawl_record={"x": 1},
            detail_api_raw=None,
        )

    assert result["raw_record_id"] == 99
    assert result["metrics_id"] == 88
    insert_raw_sql = conn.execute.call_args_list[2][0][0]
    assert "INSERT INTO crawl_raw_records" in insert_raw_sql
    insert_metrics_sql = conn.execute.call_args_list[3][0][0]
    assert "INSERT INTO seller_item_daily_metrics" in insert_metrics_sql

"""删除卖家订阅的端到端回归：真实执行 SQL，验证关联数据被清空。

与 tests/unit/test_seller_subscription_delete_cascade.py 的区别：
- 单测用打桩连接，校验「调用了哪些 SQL、顺序是否正确」；
- 本用例走 SQLite 离线替身真实执行，校验「SQL 真能跑、数据真没了」，
  并且确认不会误删**其他卖家**的数据。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.app import app

SELLER = "2221197154547"
OTHER_SELLER = "11111111111"
TASK_NAME = "seller_subscriptions"

RELATED_TABLES = (
    "seller_subscription_items",
    "seller_item_daily_metrics",
    "seller_item_metrics",
    "item_monitor_health_weekly",
    "seller_profiles",
    "item_detail_api_raw",
)


@pytest.fixture()
def api_client():
    return TestClient(app)


def _count(conn, sql: str, params: tuple) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row["c"] if isinstance(row, dict) else row[0])


def _seed_seller(conn, seller_user_id: str, raw_id: int) -> None:
    """为该卖家铺一套完整的关联数据（商品 + 日指标 + raw + 时序 + 画像 + 健康度）。"""
    conn.execute(
        "INSERT INTO crawl_raw_records (id, raw_json) VALUES (?, ?)",
        (raw_id, '{"seed": true}'),
    )
    conn.execute(
        """
        INSERT INTO seller_subscription_items
            (task_name, seller_user_id, item_id, title, price, item_status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (TASK_NAME, seller_user_id, f"item-{seller_user_id}", "商品", 9.9, "在售"),
    )
    conn.execute(
        """
        INSERT INTO seller_item_daily_metrics
            (task_name, seller_user_id, item_id, snapshot_day, want_count, view_count, raw_record_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (TASK_NAME, seller_user_id, f"item-{seller_user_id}", "2026-09-20", 1, 2, raw_id),
    )
    conn.execute(
        """
        INSERT INTO seller_item_metrics
            (task_name, seller_user_id, item_id, title, want_count, view_count)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (TASK_NAME, seller_user_id, f"item-{seller_user_id}", "商品", 1, 2),
    )
    conn.execute(
        """
        INSERT INTO item_monitor_health_weekly
            (week_start, week_end, seller_user_id, item_id, healthy, action)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("2026-09-14", "2026-09-20", seller_user_id, f"item-{seller_user_id}", 1, "kept"),
    )
    conn.execute(
        """
        INSERT INTO seller_profiles
            (task_name, seller_user_id, nickname, profile_json, profile_day)
        VALUES (?, ?, ?, ?, ?)
        """,
        (TASK_NAME, seller_user_id, "卖家", "{}", "2026-09-20"),
    )
    conn.execute(
        """
        INSERT INTO item_detail_api_raw
            (item_id, seller_user_id, task_name, raw_json)
        VALUES (?, ?, ?, ?)
        """,
        (f"item-{seller_user_id}", seller_user_id, TASK_NAME, "{}"),
    )
    conn.commit()


def _remaining(conn, seller_user_id: str) -> dict[str, int]:
    return {
        table: _count(
            conn,
            f"SELECT COUNT(*) AS c FROM {table} WHERE seller_user_id = ?",
            (seller_user_id,),
        )
        for table in RELATED_TABLES
    }


def test_delete_subscription_clears_related_rows_and_keeps_others(api_client, offline_db):
    created = api_client.post(
        "/api/seller-subscriptions",
        json={"seller_url": f"https://www.goofish.com/personal?userId={SELLER}"},
    ).json()["item"]
    subscription_id = created["id"]

    with offline_db() as conn:
        _seed_seller(conn, SELLER, raw_id=9001)
        _seed_seller(conn, OTHER_SELLER, raw_id=9002)

    response = api_client.delete(f"/api/seller-subscriptions/{subscription_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["deleted"]["seller_subscription_items"] == 1
    assert body["deleted"]["crawl_raw_records"] == 1

    with offline_db() as conn:
        # 被删卖家：所有关联表都清空
        assert _remaining(conn, SELLER) == {table: 0 for table in RELATED_TABLES}
        # 日指标删掉后，它 1:1 对应的原始记录也不能留
        assert _count(
            conn, "SELECT COUNT(*) AS c FROM crawl_raw_records WHERE id = ?", (9001,)
        ) == 0
        # 其他卖家：一行都不能少
        assert _remaining(conn, OTHER_SELLER) == {table: 1 for table in RELATED_TABLES}
        assert _count(
            conn, "SELECT COUNT(*) AS c FROM crawl_raw_records WHERE id = ?", (9002,)
        ) == 1

"""删除卖家订阅时必须级联清理该卖家名下的商品数据。"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

from src.services.seller_subscription_storage import (
    SELLER_RELATED_TABLES,
    delete_subscription_sync,
    delete_subscription_with_stats_sync,
)


class _FakeCursor:
    def __init__(self, rowcount: int = 0, rows=None, one=None):
        self.rowcount = rowcount
        self._rows = rows or []
        self._one = one

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._one


class _FakeConn:
    """记录所有 SQL，按 SQL 内容返回预设结果。"""

    def __init__(self, subscription_row, raw_rows, delete_rowcount: int = 3):
        self.subscription_row = subscription_row
        self.raw_rows = raw_rows
        self.delete_rowcount = delete_rowcount
        self.executed: list[tuple[str, tuple | None]] = []
        self.commits = 0

    def execute(self, sql: str, params=None):
        normalized = " ".join(sql.split())
        self.executed.append((normalized, tuple(params) if params else None))
        if normalized.startswith("SELECT seller_user_id FROM seller_subscriptions"):
            return _FakeCursor(one=self.subscription_row)
        if normalized.startswith("SELECT raw_record_id FROM seller_item_daily_metrics"):
            return _FakeCursor(rows=self.raw_rows)
        if normalized.startswith("DELETE FROM seller_subscriptions"):
            return _FakeCursor(rowcount=1)
        return _FakeCursor(rowcount=self.delete_rowcount)

    def commit(self):
        self.commits += 1


def _run(conn: _FakeConn, func, *args):
    @contextmanager
    def _fake_db():
        yield conn

    with (
        patch("src.services.seller_subscription_storage.bootstrap_storage"),
        patch("src.services.seller_subscription_storage.db_connection", lambda *a, **k: _fake_db()),
    ):
        return func(*args)


def _sqls(conn: _FakeConn) -> list[str]:
    return [sql for sql, _ in conn.executed]


def test_delete_cascades_all_related_tables():
    conn = _FakeConn(
        subscription_row={"seller_user_id": "u1"},
        raw_rows=[{"raw_record_id": 7}, {"raw_record_id": 8}],
    )
    result = _run(conn, delete_subscription_with_stats_sync, 42)

    assert result is not None
    assert result["seller_user_id"] == "u1"

    # 六张按 seller_user_id 归属的表都要删
    for table in SELLER_RELATED_TABLES:
        matched = [p for sql, p in conn.executed if sql == f"DELETE FROM {table} WHERE seller_user_id = ?"]
        assert matched == [("u1",)], f"{table} 未被清理"

    # seller_item_daily_metrics 删掉后，再用收集到的 raw id 清 crawl_raw_records
    raw_delete = [p for sql, p in conn.executed if sql.startswith("DELETE FROM crawl_raw_records WHERE id IN")]
    assert raw_delete == [(7, 8)]

    # 订阅行本身也要删，且必须排在关联数据之后（否则查不到 seller_user_id）
    sqls = _sqls(conn)
    sub_index = next(i for i, s in enumerate(sqls) if s.startswith("DELETE FROM seller_subscriptions"))
    for table in SELLER_RELATED_TABLES:
        first_index = next(i for i, s in enumerate(sqls) if s.startswith(f"DELETE FROM {table}"))
        assert first_index < sub_index

    assert conn.commits == 1


def test_delete_returns_counts_per_table():
    conn = _FakeConn(
        subscription_row={"seller_user_id": "u1"},
        raw_rows=[{"raw_record_id": 7}],
        delete_rowcount=5,
    )
    result = _run(conn, delete_subscription_with_stats_sync, 1)
    assert result["deleted"]["seller_subscription_items"] == 5
    assert result["deleted"]["crawl_raw_records"] == 5


def test_missing_subscription_returns_none_without_cleanup():
    conn = _FakeConn(subscription_row=None, raw_rows=[])
    assert _run(conn, delete_subscription_sync, 999) is False

    assert not [s for s in _sqls(conn) if s.startswith("DELETE")]
    assert conn.commits == 0


def test_no_raw_records_skips_crawl_raw_delete():
    conn = _FakeConn(subscription_row={"seller_user_id": "u1"}, raw_rows=[])
    result = _run(conn, delete_subscription_with_stats_sync, 1)
    assert "crawl_raw_records" not in result["deleted"]
    assert not [s for s in _sqls(conn) if "crawl_raw_records" in s]

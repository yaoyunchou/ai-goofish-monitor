"""商品级周增长聚合：SQL 形状与边界处理。

聚合逻辑依赖 PostgreSQL 的 DISTINCT ON，无法在纯内存中重放；
因此本文件覆盖两层：
  1. SQL 结构契约（占位符数量、DISTINCT ON、至少跨 2 天过滤、LEFT JOIN 主表）
  2. 后处理边界（同日开始结束、NULL 指标、days_with_data 归一）
"""
from __future__ import annotations

from datetime import date

import pytest

from src.services import seller_item_daily_storage as storage
from src.services.seller_item_daily_storage import (
    _WEEKLY_GROWTH_SQL,
    _to_iso_date,
    weekly_item_growth_sync,
)

WEEK_START = date(2026, 9, 7)
WEEK_END = date(2026, 9, 13)


# ---------------------------------------------------------------------------
# SQL 结构契约
# ---------------------------------------------------------------------------
def test_sql_placeholder_count_matches_between_clauses():
    """3 个 CTE × 2 个日期参数 = 6 个占位符。"""
    assert _WEEKLY_GROWTH_SQL.count("?") == 6


def test_sql_uses_distinct_on_for_first_and_last_seen():
    assert _WEEKLY_GROWTH_SQL.count("DISTINCT ON") == 2


def test_sql_orders_first_seen_ascending_and_last_seen_descending():
    assert "snapshot_day ASC, m.captured_at ASC" in _WEEKLY_GROWTH_SQL
    assert "snapshot_day DESC, m.captured_at DESC" in _WEEKLY_GROWTH_SQL


def test_sql_joins_item_master_for_title_and_muted_flag():
    assert "LEFT JOIN seller_subscription_items" in _WEEKLY_GROWTH_SQL
    assert "is_muted" in _WEEKLY_GROWTH_SQL


def test_sql_uses_coalesce_so_null_metrics_do_not_poison_growth():
    assert _WEEKLY_GROWTH_SQL.count("COALESCE") >= 4


def test_sql_selects_span_fields_used_for_interrupt_detection():
    for column in ("days_with_data", "first_day", "last_day"):
        assert column in _WEEKLY_GROWTH_SQL


def test_sql_balances_parentheses():
    assert _WEEKLY_GROWTH_SQL.count("(") == _WEEKLY_GROWTH_SQL.count(")")


# ---------------------------------------------------------------------------
# 日期归一
# ---------------------------------------------------------------------------
def test_to_iso_date_handles_date_object():
    assert _to_iso_date(date(2026, 9, 7)) == "2026-09-07"


def test_to_iso_date_handles_string():
    assert _to_iso_date("2026-09-07") == "2026-09-07"


def test_to_iso_date_handles_none_and_blank():
    assert _to_iso_date(None) is None
    assert _to_iso_date("   ") is None


# ---------------------------------------------------------------------------
# 后处理边界（stub 掉数据库）
# ---------------------------------------------------------------------------
class _StubConn:
    def __init__(self, rows):
        self._rows = rows
        self.last_sql: str | None = None
        self.last_params = None

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.last_params = params
        return self

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def commit(self):
        pass


class _StubCtx:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self._conn

    def __exit__(self, *exc):
        return False


@pytest.fixture()
def patch_db(monkeypatch):
    holder: dict = {}

    def _install(rows):
        conn = _StubConn(rows)
        holder["conn"] = conn
        monkeypatch.setattr(storage, "db_connection", lambda *a, **k: _StubCtx(conn))
        monkeypatch.setattr(storage, "bootstrap_storage", lambda: None)
        return conn

    return _install


def _raw_row(**overrides):
    row = {
        "seller_user_id": "s1",
        "item_id": "item1",
        "days_with_data": 7,
        "first_day": date(2026, 9, 7),
        "last_day": date(2026, 9, 13),
        "view_start": 100,
        "view_end": 105,
        "view_growth": 5,
        "want_start": 3,
        "want_end": 3,
        "want_growth": 0,
        "title": "测试商品",
        "price": 1999,
        "item_status": "在售",
        "item_link": "https://x",
        "first_seen_at": None,
        "is_muted": False,
    }
    row.update(overrides)
    return row


def test_weekly_item_growth_normalizes_row(patch_db):
    patch_db([_raw_row()])
    results = weekly_item_growth_sync(WEEK_START, WEEK_END)
    assert len(results) == 1
    row = results[0]
    assert row["first_day"] == "2026-09-07"
    assert row["last_day"] == "2026-09-13"
    assert row["days_with_data"] == 7
    assert row["view_growth"] == 5
    assert row["want_growth"] == 0
    assert row["has_metric_data"] is True
    assert row["is_muted"] is False


def test_weekly_item_growth_passes_six_params(patch_db):
    conn = patch_db([_raw_row()])
    weekly_item_growth_sync(WEEK_START, WEEK_END)
    assert conn.last_params == (
        "2026-09-07", "2026-09-13",
        "2026-09-07", "2026-09-13",
        "2026-09-07", "2026-09-13",
    )


def test_single_day_item_is_dropped(patch_db):
    """first_day == last_day → 无法算增长，必须丢弃（防御性，SQL 已过滤）。"""
    patch_db([_raw_row(first_day=date(2026, 9, 10), last_day=date(2026, 9, 10), days_with_data=1)])
    assert weekly_item_growth_sync(WEEK_START, WEEK_END) == []


def test_reversed_days_item_is_dropped(patch_db):
    patch_db([_raw_row(first_day=date(2026, 9, 13), last_day=date(2026, 9, 7))])
    assert weekly_item_growth_sync(WEEK_START, WEEK_END) == []


def test_null_metrics_mark_has_metric_data_false(patch_db):
    patch_db([_raw_row(view_start=None, view_end=None, want_start=None, want_end=None)])
    row = weekly_item_growth_sync(WEEK_START, WEEK_END)[0]
    assert row["has_metric_data"] is False


def test_partial_null_metrics_mark_has_metric_data_false(patch_db):
    patch_db([_raw_row(want_end=None)])
    row = weekly_item_growth_sync(WEEK_START, WEEK_END)[0]
    assert row["has_metric_data"] is False


def test_null_growth_is_coerced_to_zero(patch_db):
    patch_db([_raw_row(view_growth=None, want_growth=None)])
    row = weekly_item_growth_sync(WEEK_START, WEEK_END)[0]
    assert row["view_growth"] == 0
    assert row["want_growth"] == 0


def test_null_days_with_data_is_coerced_to_zero(patch_db):
    patch_db([_raw_row(days_with_data=None)])
    row = weekly_item_growth_sync(WEEK_START, WEEK_END)[0]
    assert row["days_with_data"] == 0


def test_is_muted_defaults_false_when_missing(patch_db):
    row_in = _raw_row()
    row_in.pop("is_muted")
    patch_db([row_in])
    assert weekly_item_growth_sync(WEEK_START, WEEK_END)[0]["is_muted"] is False


def test_is_muted_true_is_preserved(patch_db):
    patch_db([_raw_row(is_muted=True)])
    assert weekly_item_growth_sync(WEEK_START, WEEK_END)[0]["is_muted"] is True


def test_first_seen_at_timestamp_is_serialized(patch_db):
    from datetime import datetime

    patch_db([_raw_row(first_seen_at=datetime(2026, 8, 1, 12, 0))])
    row = weekly_item_growth_sync(WEEK_START, WEEK_END)[0]
    assert row["first_seen_at"].startswith("2026-08-01")


def test_empty_result_set(patch_db):
    patch_db([])
    assert weekly_item_growth_sync(WEEK_START, WEEK_END) == []


def test_negative_growth_is_kept_not_clamped(patch_db):
    """闲鱼侧计数可能下降（删差评/SKU 合并），负增长要如实保留供判定。"""
    patch_db([_raw_row(view_start=200, view_end=180, view_growth=-20)])
    row = weekly_item_growth_sync(WEEK_START, WEEK_END)[0]
    assert row["view_growth"] == -20

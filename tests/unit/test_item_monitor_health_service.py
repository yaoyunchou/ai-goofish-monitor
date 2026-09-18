"""商品级监控健康度判定逻辑：独立可辨识用例。

覆盖：
  - OR 口径（浏览或想要任一达标即保留）与边界值（== 阈值算达标）
  - 数据不足 / 已停用 / 指标缺失 / 新商品宽限期 → 跳过
  - 数据中断（窗口末日无数据）→ 判定 interrupted 而非不达标
  - 影子模式 dry_run 与真停用 muted 的动作区分
  - 单周停用上限熔断
  - 周界计算（周一取上一完整周）
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from src.services.item_monitor_health_service import (
    ACTION_DRY_RUN,
    ACTION_INTERRUPTED,
    ACTION_KEPT,
    ACTION_MUTED,
    ACTION_SKIPPED,
    ItemHealthDecision,
    MonitorConfig,
    build_notification_payload,
    evaluate_week,
    last_full_week,
)
from src.time_utils import SHANGHAI_TZ

WEEK_START = date(2026, 9, 7)
WEEK_END = date(2026, 9, 13)
# 判定发生在 09-18（周五），宽限期 14 天 → 早于 09-04 首次采集的商品不享宽限
NOW = datetime(2026, 9, 18, 10, 0, tzinfo=SHANGHAI_TZ)
OLD_FIRST_SEEN = "2026-08-01T00:00:00+08:00"


def make_row(
    item_id: str,
    *,
    view_growth: int = 0,
    want_growth: int = 0,
    days_with_data: int = 7,
    last_day: str | None = None,
    is_muted: bool = False,
    first_seen_at: str | None = OLD_FIRST_SEEN,
    has_metric_data: bool = True,
    seller_user_id: str = "seller-1",
) -> dict:
    view_start = 100
    want_start = 5
    return {
        "seller_user_id": seller_user_id,
        "item_id": item_id,
        "title": f"商品 {item_id}",
        "days_with_data": days_with_data,
        "first_day": WEEK_START.isoformat(),
        "last_day": last_day or WEEK_END.isoformat(),
        "view_start": view_start,
        "view_end": view_start + view_growth,
        "view_growth": view_growth,
        "want_start": want_start,
        "want_end": want_start + want_growth,
        "want_growth": want_growth,
        "is_muted": is_muted,
        "has_metric_data": has_metric_data,
        "first_seen_at": first_seen_at,
        "price": 1999,
        "item_link": "https://www.goofish.com/item?id=1",
    }


def decide_one(row: dict, *, config: MonitorConfig) -> ItemHealthDecision:
    decisions = evaluate_week(WEEK_START, WEEK_END, config=config, rows=[row], now=NOW)
    assert len(decisions) == 1
    return decisions[0]


DRY = MonitorConfig(dry_run=True)
LIVE = MonitorConfig(auto_disable_enabled=True, dry_run=False)


# ---------------------------------------------------------------------------
# OR 口径与边界
# ---------------------------------------------------------------------------
def test_view_growth_alone_keeps_item():
    decision = decide_one(make_row("a", view_growth=12, want_growth=0), config=LIVE)
    assert decision.action == ACTION_KEPT
    assert decision.healthy is True


def test_want_growth_alone_keeps_item():
    """浏览几乎不涨，但想要涨了 → OR 口径下依然保留。"""
    decision = decide_one(make_row("b", view_growth=1, want_growth=3), config=LIVE)
    assert decision.action == ACTION_KEPT


def test_boundary_view_equals_threshold_is_kept():
    """浏览增长恰好 == 10 视为达标（>= 语义）。"""
    decision = decide_one(make_row("c", view_growth=10, want_growth=0), config=LIVE)
    assert decision.action == ACTION_KEPT


def test_boundary_want_equals_threshold_is_kept():
    """想要增长恰好 == 2 视为达标。"""
    decision = decide_one(make_row("d", view_growth=0, want_growth=2), config=LIVE)
    assert decision.action == ACTION_KEPT


def test_just_below_both_thresholds_gets_muted():
    """浏览 9 < 10 且 想要 1 < 2 → 两者都低，停用。"""
    decision = decide_one(make_row("e", view_growth=9, want_growth=1), config=LIVE)
    assert decision.action == ACTION_MUTED
    assert decision.healthy is False
    assert "9 < 10" in decision.reason and "1 < 2" in decision.reason


def test_zero_growth_both_gets_muted():
    decision = decide_one(make_row("f", view_growth=0, want_growth=0), config=LIVE)
    assert decision.action == ACTION_MUTED


# ---------------------------------------------------------------------------
# 跳过条件
# ---------------------------------------------------------------------------
def test_too_few_days_is_skipped():
    decision = decide_one(make_row("g", days_with_data=1), config=LIVE)
    assert decision.action == ACTION_SKIPPED
    assert "有数据天数不足" in decision.reason


def test_already_muted_is_skipped():
    decision = decide_one(make_row("h", is_muted=True), config=LIVE)
    assert decision.action == ACTION_SKIPPED
    assert "此前已停止监控" in decision.reason


def test_missing_metric_data_is_skipped():
    decision = decide_one(make_row("i", has_metric_data=False), config=LIVE)
    assert decision.action == ACTION_SKIPPED
    assert "首末指标缺失" in decision.reason


def test_new_item_within_grace_period_is_skipped():
    recent = (NOW.date() - timedelta(days=3)).isoformat() + "T00:00:00+08:00"
    decision = decide_one(make_row("j", first_seen_at=recent), config=LIVE)
    assert decision.action == ACTION_SKIPPED
    assert "宽限期" in decision.reason


def test_item_outside_grace_period_is_judged():
    old = (NOW.date() - timedelta(days=30)).isoformat() + "T00:00:00+08:00"
    decision = decide_one(make_row("k", first_seen_at=old), config=LIVE)
    assert decision.action == ACTION_MUTED


def test_protect_days_zero_disables_grace():
    cfg = MonitorConfig(auto_disable_enabled=True, dry_run=False, protect_days=0)
    recent = (NOW.date() - timedelta(days=1)).isoformat() + "T00:00:00+08:00"
    decision = decide_one(make_row("l", first_seen_at=recent), config=cfg)
    assert decision.action == ACTION_MUTED


# ---------------------------------------------------------------------------
# 数据中断（疑似已售）
# ---------------------------------------------------------------------------
def test_interrupted_data_is_not_treated_as_unhealthy():
    """商品可能在周中卖掉了 —— 数据中断不能判为「凉了」。"""
    decision = decide_one(
        make_row("m", last_day="2026-09-10"), config=LIVE
    )
    assert decision.action == ACTION_INTERRUPTED
    assert decision.action != ACTION_MUTED
    assert "疑似已售或已下架" in decision.reason


def test_data_ending_on_week_end_is_judged_normally():
    decision = decide_one(
        make_row("n", view_growth=0, want_growth=0, last_day=WEEK_END.isoformat()),
        config=LIVE,
    )
    assert decision.action == ACTION_MUTED


# ---------------------------------------------------------------------------
# 影子模式
# ---------------------------------------------------------------------------
def test_dry_run_marks_dry_run_not_muted():
    decision = decide_one(make_row("o", view_growth=0, want_growth=0), config=DRY)
    assert decision.action == ACTION_DRY_RUN
    assert decision.action != ACTION_MUTED
    assert decision.healthy is False


def test_dry_run_does_not_affect_kept_items():
    decision = decide_one(make_row("p", view_growth=20), config=DRY)
    assert decision.action == ACTION_KEPT


# ---------------------------------------------------------------------------
# 批量与统计
# ---------------------------------------------------------------------------
def test_evaluate_week_handles_mixed_batch():
    rows = [
        make_row("keep1", view_growth=15),
        make_row("keep2", want_growth=5),
        make_row("mute1", view_growth=1, want_growth=0),
        make_row("mute2", view_growth=0, want_growth=1),
        make_row("skip1", days_with_data=1),
        make_row("gone1", last_day="2026-09-09"),
    ]
    decisions = evaluate_week(WEEK_START, WEEK_END, config=LIVE, rows=rows, now=NOW)
    by_action: dict[str, list[str]] = {}
    for decision in decisions:
        by_action.setdefault(decision.action, []).append(decision.item_id)

    assert sorted(by_action[ACTION_KEPT]) == ["keep1", "keep2"]
    assert sorted(by_action[ACTION_MUTED]) == ["mute1", "mute2"]
    assert by_action[ACTION_SKIPPED] == ["skip1"]
    assert by_action[ACTION_INTERRUPTED] == ["gone1"]


def test_evaluate_week_empty_rows_returns_empty():
    assert evaluate_week(WEEK_START, WEEK_END, config=LIVE, rows=[], now=NOW) == []


def test_decisions_carry_week_bounds_and_growth_snapshot():
    decision = decide_one(make_row("q", view_growth=3, want_growth=1), config=LIVE)
    row = decision.to_row()
    assert row["week_start"] == WEEK_START.isoformat()
    assert row["week_end"] == WEEK_END.isoformat()
    assert row["view_growth"] == 3
    assert row["want_growth"] == 1
    assert row["action"] == ACTION_MUTED


# ---------------------------------------------------------------------------
# 周界计算
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "today,expected_start",
    [
        (date(2026, 9, 18), date(2026, 9, 7)),   # 周五 → 上一整周
        (date(2026, 9, 14), date(2026, 9, 7)),   # 周一 → 上一整周（本周不算完整）
        (date(2026, 9, 13), date(2026, 8, 31)),  # 周日 → 上一个已结束的整周起点
        (date(2026, 9, 21), date(2026, 9, 14)),  # 下周一
    ],
)
def test_last_full_week_is_monday_to_sunday(today, expected_start):
    week_start, week_end = last_full_week(today)
    assert week_start == expected_start
    assert week_start.weekday() == 0  # 周一
    assert week_end.weekday() == 6    # 周日
    assert (week_end - week_start).days == 6


def test_protect_days_hardened_minimum_days():
    """MIN_DAYS_WITH_DATA 至少为 2，防止把单点数据当增长。"""
    cfg = MonitorConfig(min_days_with_data=1)
    assert cfg.min_days_with_data >= 1  # dataclass 本身不强制，from_env 才钳制


def test_monitor_config_from_env_respects_safe_defaults(monkeypatch):
    for key in (
        "MONITOR_AUTO_DISABLE_ENABLED",
        "MONITOR_DRY_RUN",
        "MONITOR_KEEP_VIEW_GROWTH",
        "MONITOR_KEEP_WANT_GROWTH",
        "MONITOR_MIN_DAYS_WITH_DATA",
        "MONITOR_PROTECT_DAYS",
        "MONITOR_MAX_MUTE_PER_WEEK",
    ):
        monkeypatch.delenv(key, raising=False)
    cfg = MonitorConfig.from_env()
    assert cfg.auto_disable_enabled is False
    assert cfg.dry_run is True
    assert cfg.keep_view_growth == 10
    assert cfg.keep_want_growth == 2
    assert cfg.min_days_with_data == 2
    assert cfg.protect_days == 14
    assert cfg.max_mute_per_week == 0


def test_monitor_config_from_env_reads_overrides(monkeypatch):
    monkeypatch.setenv("MONITOR_AUTO_DISABLE_ENABLED", "true")
    monkeypatch.setenv("MONITOR_DRY_RUN", "false")
    monkeypatch.setenv("MONITOR_KEEP_VIEW_GROWTH", "25")
    monkeypatch.setenv("MONITOR_KEEP_WANT_GROWTH", "4")
    monkeypatch.setenv("MONITOR_MIN_DAYS_WITH_DATA", "1")  # 应被钳制到 2
    monkeypatch.setenv("MONITOR_MAX_MUTE_PER_WEEK", "5")
    cfg = MonitorConfig.from_env()
    assert cfg.auto_disable_enabled is True
    assert cfg.dry_run is False
    assert cfg.keep_view_growth == 25
    assert cfg.keep_want_growth == 4
    assert cfg.min_days_with_data == 2
    assert cfg.max_mute_per_week == 5


# ---------------------------------------------------------------------------
# 通知文案
# ---------------------------------------------------------------------------
def test_notification_payload_lists_items_and_truncates():
    muted = [
        ItemHealthDecision(
            seller_user_id=f"s{i}",
            item_id=f"item{i}",
            title=f"商品标题{i}",
            week_start=WEEK_START,
            week_end=WEEK_END,
            days_with_data=6,
            view_growth=1,
            want_growth=0,
            healthy=False,
            reason="不达标",
            action=ACTION_MUTED,
            price="1999",
        )
        for i in range(15)
    ]
    payload = build_notification_payload(
        muted, week_start=WEEK_START, week_end=WEEK_END, dry_run=False, limit=10
    )
    assert "15" in payload["商品标题"]
    assert "已停止监控" in payload["商品标题"]
    assert "另有 5 个" in payload["data_content"]


def test_notification_payload_dry_run_wording():
    muted = [
        ItemHealthDecision(
            seller_user_id="s1",
            item_id="i1",
            title="t",
            week_start=WEEK_START,
            week_end=WEEK_END,
            healthy=False,
            action=ACTION_DRY_RUN,
        )
    ]
    payload = build_notification_payload(
        muted, week_start=WEEK_START, week_end=WEEK_END, dry_run=True
    )
    assert "试运行" in payload["商品标题"]

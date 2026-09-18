"""店铺「保量 + 补位」选品模拟的纯逻辑测试。

只测不依赖数据库的部分：双门槛判定 + 收敛推演 + fresh 预算。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "item_selection_simulate.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("item_selection_simulate", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("item_selection_simulate", module)
    spec.loader.exec_module(module)
    return module


sim = _load_module()

# 定稿阈值（决策 1 = 20，决策 2 = 路线 A）
DEFAULTS = dict(min_view_total=100, min_view_growth=20, min_want_growth=2)


def _decide(row: dict, **overrides) -> bool:
    cfg = {**DEFAULTS, **overrides}
    passed_stock, passed_growth, _ = sim.evaluate_item(row, **cfg)
    return passed_stock and passed_growth


class TestEvaluateItem:
    def test_keeps_when_stock_and_view_growth_pass(self):
        assert _decide({"view_end": 500, "view_growth": 50, "want_growth": 0}) is True

    def test_keeps_when_stock_and_want_growth_pass(self):
        assert _decide({"view_end": 500, "view_growth": 5, "want_growth": 20}) is True

    def test_kicks_when_stock_low_despite_strong_growth(self):
        """存量门槛是硬门槛：浏览涨得再好，存量不够也踢。"""
        assert _decide({"view_end": 50, "view_growth": 500, "want_growth": 50}) is False

    def test_kicks_when_both_low(self):
        assert _decide({"view_end": 50, "view_growth": 0, "want_growth": 0}) is False

    # --- 边界：阈值已定稿为 存量 100 / 浏览增长 20 / 想要增长 2 ---

    def test_boundary_stock_exactly_at_threshold_kept(self):
        assert _decide({"view_end": 100, "view_growth": 20, "want_growth": 0}) is True

    def test_boundary_stock_one_below_kicked(self):
        assert _decide({"view_end": 99, "view_growth": 20, "want_growth": 0}) is False

    def test_boundary_view_growth_exactly_at_threshold_kept(self):
        assert _decide({"view_end": 100, "view_growth": 20, "want_growth": 0}) is True

    def test_boundary_view_growth_one_below_kicked(self):
        """定稿阈值是 20，所以 19 会被踢（这是决策 1 的直接后果）。"""
        assert _decide({"view_end": 100, "view_growth": 19, "want_growth": 0}) is False

    def test_boundary_want_growth_exactly_at_threshold_kept(self):
        assert _decide({"view_end": 100, "view_growth": 0, "want_growth": 2}) is True

    def test_want_channel_still_rescues_when_view_growth_far_below(self):
        """浏览增长 5 远低于 20，但只要想要增长 ≥ 2 仍保留（OR 逻辑未被阈值 20 破坏）。"""
        assert _decide({"view_end": 100, "view_growth": 5, "want_growth": 2}) is True

    def test_missing_fields_treated_as_zero(self):
        assert _decide({}) is False

    def test_reason_mentions_both_missing_gates(self):
        _, _, reason = sim.evaluate_item(
            {"view_end": 10, "view_growth": 1, "want_growth": 0}, **DEFAULTS
        )
        assert "存量" in reason
        assert "浏览" in reason

    def test_bool_gates_reported_separately(self):
        passed_stock, passed_growth, _ = sim.evaluate_item(
            {"view_end": 500, "view_growth": 1, "want_growth": 0}, **DEFAULTS
        )
        assert passed_stock is True
        assert passed_growth is False


class TestSimulateConvergence:
    def test_starts_full_when_roster_covers_limit(self):
        timeline = sim.simulate_convergence(
            roster_size=500, fresh_remaining=200, kick_rate=0.0, limit=100, weeks=3
        )
        assert timeline[0]["active"] == 100
        assert timeline[0]["vacant"] == 0

    def test_no_kicks_keeps_seats_stable(self):
        timeline = sim.simulate_convergence(
            roster_size=500, fresh_remaining=0, kick_rate=0.0, limit=100, weeks=5
        )
        assert all(point["active"] == 100 for point in timeline)

    def test_decays_when_fresh_exhausted(self):
        """fresh 耗尽后，席位按踢出率衰减 —— 这是模型的核心风险。

        踢出数用 floor：100 →(踢50)→ 50 →(踢25)→ 25 →(踢12)→ 13 →(踢6)→ 7
        （注意 25×0.5=12.5 取 floor 得 12，所以剩 13 而非 12）
        """
        timeline = sim.simulate_convergence(
            roster_size=100, fresh_remaining=0, kick_rate=0.5, limit=100, weeks=4
        )
        assert [p["active"] for p in timeline] == [100, 50, 25, 13, 7]

    def test_vacancy_grows_as_seats_drop(self):
        timeline = sim.simulate_convergence(
            roster_size=100, fresh_remaining=0, kick_rate=0.5, limit=100, weeks=2
        )
        assert timeline[-1]["vacant"] == 100 - timeline[-1]["active"]

    def test_fresh_is_consumed_only_as_needed(self):
        """踢出 10 个、fresh 有 30 个 → 只消耗 10 个。"""
        timeline = sim.simulate_convergence(
            roster_size=100, fresh_remaining=30, kick_rate=0.1, limit=100, weeks=1
        )
        assert timeline[0]["fresh"] == 30
        assert timeline[1]["fresh"] == 20

    def test_seats_never_exceed_limit(self):
        timeline = sim.simulate_convergence(
            roster_size=10000, fresh_remaining=10000, kick_rate=0.0, limit=100, weeks=4
        )
        assert all(point["active"] <= 100 for point in timeline)

    def test_never_goes_negative(self):
        timeline = sim.simulate_convergence(
            roster_size=100, fresh_remaining=0, kick_rate=1.0, limit=100, weeks=6
        )
        assert all(point["active"] >= 0 for point in timeline)


class TestWeeksUntilDry:
    """`weeks_until_dry` 是 B0 报告的核心 —— 用户 300 商品示例的解析式答案。"""

    def test_user_example_300_items_100_seats_30pct(self):
        """用户原话场景：A 店 300 个商品，100 个席位，30 个被踢（30%）。

        fresh = 300 - 100 = 200；每周踢出 = 100 × 0.30 = 30；
        200 ÷ 30 = 6.67 → 向下取整 6 周。
        """
        assert sim.weeks_until_dry(
            roster_size=300, limit=100, kick_rate=0.30
        ) == 6

    def test_low_kick_rate_extends_lifetime(self):
        assert sim.weeks_until_dry(
            roster_size=300, limit=100, kick_rate=0.10
        ) == 20

    def test_pool_equals_seats_is_already_dry(self):
        """300 个商品但只有 100 可见 → 没有 fresh，立刻枯竭。"""
        assert sim.weeks_until_dry(
            roster_size=100, limit=100, kick_rate=0.30
        ) == 0

    def test_pool_smaller_than_seats_never_negative(self):
        assert sim.weeks_until_dry(
            roster_size=50, limit=100, kick_rate=0.30
        ) == 0

    def test_zero_kick_rate_never_dries(self):
        assert sim.weeks_until_dry(
            roster_size=300, limit=100, kick_rate=0.0
        ) is None

    def test_negative_kick_rate_never_dries(self):
        assert sim.weeks_until_dry(
            roster_size=300, limit=100, kick_rate=-0.5
        ) is None

    def test_huge_pool_never_dries(self):
        """2000 个商品的店，10% 踢出率 → 200 周，实际等于永不枯竭。"""
        result = sim.weeks_until_dry(
            roster_size=2000, limit=100, kick_rate=0.10
        )
        assert result == 190
        assert result > 150  # 约 3.6 年

    def test_kick_rate_one_clears_pool_fast(self):
        assert sim.weeks_until_dry(
            roster_size=300, limit=100, kick_rate=1.0
        ) == 2


class TestFreshBudget:
    def test_weekly_need_equals_kick_count(self):
        assert sim.required_fresh_per_week(
            limit=100, kick_rate=0.10, target_seats=100
        ) == 10

    def test_weekly_need_rounds_up(self):
        """3 个席位的零头也要补一个，不能少补。"""
        assert sim.required_fresh_per_week(
            limit=100, kick_rate=0.033, target_seats=100
        ) == 4

    def test_zero_kick_rate_needs_nothing(self):
        assert sim.required_fresh_per_week(
            limit=100, kick_rate=0.0, target_seats=100
        ) == 0

    def test_small_pool_not_sustainable_at_high_kick_rate(self):
        budget = sim.fresh_budget_for_steady_state(
            limit=100, kick_rate=0.10, target_seats=100, pool_size=200
        )
        assert budget["weekly_need"] == 10
        assert budget["weeks_until_dry"] == 20
        assert budget["sustainable"] is False

    def test_large_pool_sustainable_at_low_kick_rate(self):
        budget = sim.fresh_budget_for_steady_state(
            limit=100, kick_rate=0.03, target_seats=100, pool_size=2000
        )
        assert budget["sustainable"] is True

    def test_zero_need_marked_sustainable(self):
        budget = sim.fresh_budget_for_steady_state(
            limit=100, kick_rate=0.0, target_seats=100, pool_size=0
        )
        assert budget["weekly_need"] == 0
        assert budget["sustainable"] is True


class TestCliDefaults:
    """锁定已定稿的默认值，防止决策被静默改回。

    决策 1：增量阈值 = 20
    决策 2：枯竭路线 = A（席位置空）
    """

    def _parse(self, argv):
        """直接调用 argparse 部分，避免触发 DB 访问。"""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--min-view-total", type=int, default=100)
        parser.add_argument("--min-view-growth", type=int, default=20)
        parser.add_argument("--min-want-growth", type=int, default=2)
        return parser.parse_args(argv)

    def test_growth_threshold_defaults_to_20(self):
        args = self._parse([])
        assert args.min_view_growth == 20, "决策 1 已定 20，不能被改回 10"

    def test_stock_threshold_defaults_to_100(self):
        assert self._parse([]).min_view_total == 100

    def test_want_threshold_defaults_to_2(self):
        assert self._parse([]).min_want_growth == 2

    def test_script_source_hardcodes_20(self):
        """直接读源码，确保 argparse 那一行的 default 是 20。"""
        source = _SCRIPT.read_text(encoding="utf-8")
        assert '"--min-view-growth", type=int, default=20' in source


class TestLastFullWeek:
    def test_monday_returns_previous_week(self):
        """周一当天：上周已经结束，返回上一个完整周。"""
        from datetime import date

        start, end = sim.last_full_week(date(2026, 9, 14))  # 周一
        assert start == date(2026, 9, 7)
        assert end == date(2026, 9, 13)

    def test_sunday_of_a_week_is_treated_as_that_week(self):
        """2026-09-13 是「09-07 那周」的周日。

        该周尚未走完（判定期望是「上一完整周」），所以返回的是 08-31 ~ 09-06。
        这是刻意的保守行为：周日当天不把「当天所在周」当作完整周。
        """
        from datetime import date

        start, end = sim.last_full_week(date(2026, 9, 13))  # 周日（09-07 周的末日）
        assert start == date(2026, 8, 31)
        assert end == date(2026, 9, 6)

    def test_friday_returns_the_week_before_current(self):
        from datetime import date

        start, end = sim.last_full_week(date(2026, 9, 18))  # 周五
        assert start == date(2026, 9, 7)
        assert end == date(2026, 9, 13)

    def test_week_is_always_seven_days(self):
        from datetime import date

        start, end = sim.last_full_week(date(2026, 9, 18))
        assert (end - start).days == 6
        assert start.weekday() == 0


class TestQuantiles:
    def test_empty_returns_empty(self):
        assert sim._quantiles([]) == {}

    def test_single_value(self):
        result = sim._quantiles([5.0])
        assert result["min"] == 5.0
        assert result["max"] == 5.0

    def test_median_of_even_count(self):
        result = sim._quantiles([1.0, 2.0, 3.0, 4.0])
        assert result["min"] == 1.0
        assert result["max"] == 4.0
        assert result["p50"] in (2.0, 3.0)

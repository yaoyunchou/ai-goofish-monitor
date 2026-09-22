"""累计已售的高水位差值。缺基线返回 None，不把空写成 0。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from src.time_utils import SHANGHAI_TZ


@dataclass(frozen=True)
class SnapshotPoint:
    captured_at: datetime
    sold: int | None
    price: float | None = None


@dataclass(frozen=True)
class Delta:
    delta: int | None
    incomplete: bool
    fuzzy_amount: float | None


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=SHANGHAI_TZ)
    return value.astimezone(SHANGHAI_TZ)


def high_water(points: Iterable[SnapshotPoint], upto: datetime) -> int | None:
    """截至 upto（含）的最大累计已售。没有可信读数时返回 None。"""
    limit = _aware(upto)
    values = [
        point.sold
        for point in points
        if point.sold is not None and _aware(point.captured_at) <= limit
    ]
    if not values:
        return None
    return max(values)


def _latest_price(points: Iterable[SnapshotPoint], start: datetime, end: datetime) -> float | None:
    start_at = _aware(start)
    end_at = _aware(end)
    chosen: tuple[datetime, float] | None = None
    for point in points:
        if point.price is None:
            continue
        captured = _aware(point.captured_at)
        if captured < start_at or captured > end_at:
            continue
        if chosen is None or captured >= chosen[0]:
            chosen = (captured, point.price)
    return None if chosen is None else chosen[1]


def delta_from_levels(
    hw_start: int | None,
    hw_end: int | None,
    first_sold: int | None = None,
    *,
    allow_incomplete_baseline: bool = False,
    price: float | None = None,
) -> Delta:
    """用已经算好的高水位做差。规则与 delta_between 相同，供看板批量 SQL 复用。"""
    if hw_end is None or hw_start is None:
        if not allow_incomplete_baseline or hw_end is None or first_sold is None:
            return Delta(delta=None, incomplete=True, fuzzy_amount=None)
        delta = hw_end - first_sold
        return Delta(delta=delta, incomplete=True, fuzzy_amount=_fuzzy(delta, price))
    delta = hw_end - hw_start
    return Delta(delta=delta, incomplete=False, fuzzy_amount=_fuzzy(delta, price))


def _fuzzy(delta: int | None, price: float | None) -> float | None:
    if delta is None or price is None:
        return None
    return round(delta * price, 2)


def delta_between(
    points: list[SnapshotPoint],
    start: datetime,
    end: datetime,
    *,
    allow_incomplete_baseline: bool = False,
) -> Delta:
    """区间增量 = 终点高水位 − 起点高水位。

    任一侧没有高水位时返回 delta=None，不把空写成 0。
    allow_incomplete_baseline 时，起点缺失但区间内已有第一条真实快照，
    用它做基线并标 incomplete（当天中途才开始监控）。
    """
    start_at = _aware(start)
    end_at = _aware(end)
    hw_start = high_water(points, start_at)
    hw_end = high_water(points, end_at)
    if hw_end is None or hw_start is None:
        if not allow_incomplete_baseline or hw_end is None:
            return Delta(delta=None, incomplete=True, fuzzy_amount=None)
        first = _first_in_range(points, start_at, end_at)
        if first is None or first.sold is None:
            return Delta(delta=None, incomplete=True, fuzzy_amount=None)
        delta = hw_end - first.sold
        price = _latest_price(points, first.captured_at, end_at)
        return Delta(delta=delta, incomplete=True, fuzzy_amount=_fuzzy(delta, price))
    delta = hw_end - hw_start
    price = _latest_price(points, start_at, end_at)
    return Delta(delta=delta, incomplete=False, fuzzy_amount=_fuzzy(delta, price))


def _first_in_range(
    points: list[SnapshotPoint],
    start: datetime,
    end: datetime,
) -> SnapshotPoint | None:
    chosen: SnapshotPoint | None = None
    for point in points:
        if point.sold is None:
            continue
        captured = _aware(point.captured_at)
        if captured <= start or captured > end:
            continue
        if chosen is None or captured < _aware(chosen.captured_at):
            chosen = point
    return chosen


def day_start(now: datetime) -> datetime:
    current = _aware(now)
    return current.replace(hour=0, minute=0, second=0, microsecond=0)


def floor_hour(now: datetime) -> datetime:
    current = _aware(now)
    return current.replace(minute=0, second=0, microsecond=0)


def window_stats(points: list[SnapshotPoint], now: datetime) -> dict:
    """今日 / 昨日 / 上小时 / 当前高水位。"""
    current = _aware(now)
    today0 = day_start(current)
    yesterday0 = today0 - timedelta(days=1)
    this_hour = floor_hour(current)
    prev_hour = this_hour - timedelta(hours=1)
    today = delta_between(points, today0, current, allow_incomplete_baseline=True)
    yesterday = delta_between(points, yesterday0, today0, allow_incomplete_baseline=True)
    last_hour = delta_between(points, prev_hour, this_hour, allow_incomplete_baseline=True)
    return {
        "sold_total": high_water(points, current),
        "today": today.delta,
        "today_incomplete": today.incomplete if today.delta is not None else False,
        "today_fuzzy": today.fuzzy_amount,
        "yesterday": yesterday.delta,
        "yesterday_incomplete": yesterday.incomplete if yesterday.delta is not None else False,
        "last_hour": last_hour.delta,
        "last_hour_incomplete": last_hour.incomplete if last_hour.delta is not None else False,
    }


def hourly_series(points: list[SnapshotPoint], day: datetime, now: datetime) -> list[dict]:
    """某日 24 个整点增量。未来小时为 null。当前未结束的小时标 incomplete。"""
    start_day = day_start(day)
    current = _aware(now)
    rows: list[dict] = []
    for hour in range(24):
        start = start_day + timedelta(hours=hour)
        end = start + timedelta(hours=1)
        label = start.strftime("%H:00")
        if start > current:
            rows.append({"label": label, "delta": None, "incomplete": False, "fuzzy_amount": None})
            continue
        end_at = current if end > current else end
        item = delta_between(points, start, end_at, allow_incomplete_baseline=True)
        incomplete = item.incomplete or end > current
        rows.append(
            {
                "label": label,
                "delta": item.delta,
                "incomplete": incomplete if item.delta is not None else item.incomplete,
                "fuzzy_amount": item.fuzzy_amount,
            }
        )
    return rows


def daily_series(points: list[SnapshotPoint], now: datetime, days: int = 7) -> list[dict]:
    current = _aware(now)
    today0 = day_start(current)
    rows: list[dict] = []
    for offset in range(days - 1, -1, -1):
        start = today0 - timedelta(days=offset)
        end = start + timedelta(days=1)
        end_at = current if start == today0 else end
        item = delta_between(points, start, end_at, allow_incomplete_baseline=True)
        rows.append(
            {
                "label": start.strftime("%m-%d"),
                "delta": item.delta,
                "incomplete": item.incomplete,
                "fuzzy_amount": item.fuzzy_amount,
            }
        )
    return rows

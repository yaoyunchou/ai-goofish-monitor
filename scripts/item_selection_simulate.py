"""店铺「保量 + 补位」选品模拟（只读，不改任何数据）。

模型（按 2026-09-18 澄清）
------------------------
每店席位固定 100；不达标的踢出，用**从未采集过**的商品补位。
「被筛掉过 = 已采集过」，所以 `seller_subscription_items` 里有的商品一律
不再作为补位来源 → 候选池**单调递减**，最终收敛、席位空出。
**没有冷却回归**（这是与上一版设计的关键区别）。

跑法
----
    python -m scripts.item_selection_simulate
    python -m scripts.item_selection_simulate --limit 100 --min-view-total 100
    python -m scripts.item_selection_simulate --weeks 8
    python -m scripts.item_selection_simulate --out report.md

报告
----
  B1 fresh 池剩余（每店还能补几个）—— **最关键：池子会不会很快枯竭**
  B2 存量门槛（view_total）分布与切线
  B3 本周会被踢出几个 / 留存率
  B4 补位供需对照（fresh 够不够）
  B5 收敛预测（按当前踢出率，N 周后席位规模）
  B6 两个门槛各自挡住多少（哪个是主导约束）
  B7 口径校验（存量 vs 增长）

严格只读：仅执行 SELECT。
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from typing import Any, Iterable

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.infrastructure.persistence.db_connection import db_connection  # noqa: E402
from src.services.seller_item_daily_storage import (  # noqa: E402
    _WEEKLY_GROWTH_SQL,
    _to_iso_date,
)
from src.time_utils import shanghai_today  # noqa: E402


def last_full_week(today: date | None = None) -> tuple[date, date]:
    """上一个完整自然周（周一 ~ 周日，Asia/Shanghai）。周一当天取上一周。"""
    current = today or shanghai_today()
    this_monday = current - timedelta(days=current.weekday())
    last_monday = this_monday - timedelta(days=7)
    return last_monday, last_monday + timedelta(days=6)


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# 纯逻辑（可单测，不依赖 DB）
# ---------------------------------------------------------------------------
def evaluate_item(
    row: dict[str, Any],
    *,
    min_view_total: int,
    min_view_growth: int,
    min_want_growth: int,
) -> tuple[bool, bool, str]:
    """双门槛判定。

    返回 (passed_stock, passed_growth, reason)

    保留条件（两个都要过）：
      - 存量：view_end >= min_view_total
      - 增量：view_growth >= min_view_growth  或  want_growth >= min_want_growth
    """
    view_total = _as_int(row.get("view_end"))
    view_growth = _as_int(row.get("view_growth"))
    want_growth = _as_int(row.get("want_growth"))

    passed_stock = view_total >= min_view_total
    growth_ok_view = view_growth >= min_view_growth
    growth_ok_want = want_growth >= min_want_growth
    passed_growth = growth_ok_view or growth_ok_want

    if passed_stock and passed_growth:
        hits = []
        if growth_ok_view:
            hits.append(f"浏览 +{view_growth}")
        if growth_ok_want:
            hits.append(f"想要 +{want_growth}")
        return True, True, f"达标：存量 {view_total} ≥ {min_view_total}，且 {'、'.join(hits)}"

    misses = []
    if not passed_stock:
        misses.append(f"存量 {view_total} < {min_view_total}")
    if not passed_growth:
        misses.append(
            f"浏览 +{view_growth} < {min_view_growth} 且 想要 +{want_growth} < {min_want_growth}"
        )
    return passed_stock, passed_growth, "不达标：" + "；".join(misses)


def simulate_convergence(
    *,
    roster_size: int,
    fresh_remaining: int,
    kick_rate: float,
    limit: int,
    weeks: int,
) -> list[dict[str, int]]:
    """按当前踢出率滚动推演席位规模（不依赖 DB，便于单测）。

    模型（严格对齐 R1–R7）：
      - `active` = 当前在监控的商品数（≤ limit）
      - 每轮踢出 active × kick_rate 个
      - 补位来源只有 `fresh`（在售总数 − 累计已采数），**只减不增**
      - `fresh` 耗尽后席位只能继续降 → 指数衰减

    > `roster_size` 是**在售商品总数**（如 300），不是席位数。
    > 这是与 v2 的关键区别：候选池是"店铺在售总数"，不是 `item_limit`。

    踢出数用 `int()`（floor）而非 `round()`：避免 Python 银行家舍入在 .5 处的
    不可预期行为（`round(25*0.5) == 12` 而非 13），也让推演结果单调可控。
    """
    active = min(limit, roster_size)
    fresh = max(0, fresh_remaining)
    timeline: list[dict[str, int]] = []
    for week in range(weeks + 1):
        timeline.append({
            "week": week,
            "active": active,
            "fresh": fresh,
            "seats_used": active,
            "vacant": max(0, limit - active),
        })
        kicked = int(active * kick_rate)
        refill = min(kicked, fresh)
        active = active - kicked + refill
        fresh -= refill
    return timeline


def weeks_until_dry(
    *,
    roster_size: int,
    limit: int,
    kick_rate: float,
) -> int | None:
    """解析式估算 `fresh` 池耗尽需要多少周，None 表示永不耗尽。

    近似公式：`fresh ÷ 每周踢出量`

    为什么是近似：席位在补位期间保持满员（= limit），所以每周踢出量恒定，
    直到 fresh 耗尽那一刻。因此第一次耗尽的时间可以解析求出。

    这是**最关键的单个数字** —— 它决定这个店还能"正常运转"多久。
    """
    fresh = max(0, roster_size - min(limit, roster_size))
    if fresh <= 0:
        return 0
    if kick_rate <= 0:
        return None
    weekly_kick = limit * kick_rate
    if weekly_kick <= 0:
        return None
    return int(fresh / weekly_kick)


def required_fresh_per_week(
    *,
    limit: int,
    kick_rate: float,
    target_seats: int,
) -> int:
    """维持 `target_seats` 个席位需要每周补充多少 fresh。

    稳态条件：每周补进来的 ≈ 每周踢掉的。
    踢掉数 = target_seats × kick_rate；向上取整（宁多补，不少补）。
    """
    raw = target_seats * kick_rate
    return int(raw) + (1 if raw > int(raw) else 0)


def fresh_budget_for_steady_state(
    *,
    limit: int,
    kick_rate: float,
    target_seats: int,
    pool_size: int,
) -> dict[str, Any]:
    """给定店铺商品总量，判断能否维持目标席位。

    返回：
      weekly_need      稳态每周需补多少
      weeks_until_dry  池子耗尽需要多少周
      sustainable      是否能长期维持 target_seats
    """
    weekly_need = required_fresh_per_week(
        limit=limit, kick_rate=kick_rate, target_seats=target_seats
    )
    if weekly_need <= 0:
        return {
            "weekly_need": 0,
            "weeks_until_dry": -1,
            "sustainable": True,
        }
    weeks_until_dry = pool_size // weekly_need if weekly_need else -1
    return {
        "weekly_need": weekly_need,
        "weeks_until_dry": weeks_until_dry,
        "sustainable": pool_size >= weekly_need * 52,
    }


def _quantiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    n = len(ordered)

    def at(ratio: float) -> float:
        return ordered[min(n - 1, max(0, int(round(ratio * (n - 1)))))]

    return {
        "min": ordered[0], "p25": at(.25), "p50": at(.50),
        "p75": at(.75), "p90": at(.90), "max": ordered[-1],
    }


def _fmt(value: float) -> str:
    return f"{value:,.0f}" if abs(value) >= 100 else f"{value:,.1f}"


# ---------------------------------------------------------------------------
# DB 取数
# ---------------------------------------------------------------------------
def fetch_week(week_start: date, week_end: date) -> list[dict[str, Any]]:
    params = (
        week_start.isoformat(), week_end.isoformat(),
        week_start.isoformat(), week_end.isoformat(),
        week_start.isoformat(), week_end.isoformat(),
    )
    with db_connection() as conn:
        rows = conn.execute(_WEEKLY_GROWTH_SQL, params).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["seller_user_id"] = str(payload.get("seller_user_id") or "")
        payload["item_id"] = str(payload.get("item_id") or "")
        for key in ("view_growth", "want_growth", "view_end", "want_end", "days_with_data"):
            payload[key] = _as_int(payload.get(key))
        payload["first_day"] = _to_iso_date(payload.get("first_day"))
        payload["last_day"] = _to_iso_date(payload.get("last_day"))
        out.append(payload)
    return out


def fetch_captured_counts() -> dict[str, int]:
    """每店**已采集过**的商品数（= seller_subscription_items 行数）。

    这是 fresh 池的反面：采过的永不再补。
    """
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT seller_user_id, COUNT(*) AS captured
            FROM seller_subscription_items
            GROUP BY seller_user_id
            """
        ).fetchall()
    return {str(r["seller_user_id"]): int(r["captured"] or 0) for r in rows}


def fetch_discovered_ids(seller_user_id: str) -> set[str]:
    """该店在主页列表里**出现过**的 item_id（从原始记录里挖）。

    用途：估算主页可见范围，从而推算 fresh 池上限。
    若原始记录里没有列表数据，返回空集合（报告会以其它依据兜底）。
    """
    try:
        with db_connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT r.raw_json
                FROM crawl_raw_records r
                JOIN seller_item_daily_metrics m ON m.raw_record_id = r.id
                WHERE m.seller_user_id = ?
                LIMIT 200
                """,
                (seller_user_id,),
            ).fetchall()
    except Exception:
        return set()

    found: set[str] = set()
    for row in rows:
        raw = row["raw_json"]
        if not isinstance(raw, str):
            continue
        for marker in ('"itemId"', '"商品ID"'):
            start = 0
            while True:
                idx = raw.find(marker, start)
                if idx < 0:
                    break
                start = idx + len(marker)
                chunk = raw[start:start + 40]
                quote_start = chunk.find('"')
                if quote_start < 0:
                    continue
                quote_end = chunk.find('"', quote_start + 1)
                if quote_end < 0:
                    continue
                value = chunk[quote_start + 1:quote_end]
                if value and value.isdigit():
                    found.add(value)
    return found


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------
def build_report(
    weeks: int,
    *,
    limit: int,
    min_view_total: int,
    min_view_growth: int,
    min_want_growth: int,
    pool_factor: int,
    forecast_weeks: int,
) -> str:
    today = shanghai_today()
    current_week = last_full_week(today)
    lines: list[str] = []
    add = lines.append

    add("# 店铺「保量 + 补位」选品模拟（只读）")
    add("")
    add(f"- 生成时间：{today} (Asia/Shanghai)")
    add(f"- 席位/店：**{limit}**")
    add(f"- 存量门槛：`view_total ≥ {min_view_total}`（保证有浏览量）")
    add(f"- 增量门槛：`浏览增长 ≥ {min_view_growth}` **或** `想要增长 ≥ {min_want_growth}`")
    add(f"- 候选池放大：**{pool_factor}×**（主页需抓 {limit * pool_factor} 条）")
    add(f"- 收敛预测窗口：{forecast_weeks} 周")
    add("- 枯竭路线：**A（席位置空，不为凑数采烂商品）**")
    add("")
    add("> 模型要点：被筛掉 = 已采集过 = **永不回补**。候选池单调递减，最终收敛。**无冷却回归。**")
    add("")

    try:
        captured_by_seller = fetch_captured_counts()
    except Exception as exc:
        add(f"> ⚠️ 读取已采集合失败：{exc}")
        captured_by_seller = {}

    windows: list[tuple[date, date]] = []
    for offset in range(weeks - 1, -1, -1):
        ws = current_week[0] - timedelta(days=7 * offset)
        windows.append((ws, ws + timedelta(days=6)))

    for week_start, week_end in windows:
        add(f"## 窗口 {week_start} ~ {week_end}")
        add("")
        try:
            rows = fetch_week(week_start, week_end)
        except Exception as exc:
            add(f"> ⚠️ 读取失败：{exc}")
            add("")
            continue

        if not rows:
            add("该窗口无数据。")
            add("")
            continue

        by_seller: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_seller.setdefault(row["seller_user_id"], []).append(row)

        # 先算踢出率（B0 需要用到）
        stock_fail = growth_fail = both_pass = 0
        for row in rows:
            p_stock, p_growth, _ = evaluate_item(
                row,
                min_view_total=min_view_total,
                min_view_growth=min_view_growth,
                min_want_growth=min_want_growth,
            )
            if p_stock and p_growth:
                both_pass += 1
            else:
                if not p_stock:
                    stock_fail += 1
                if not p_growth:
                    growth_fail += 1
        kicked = len(rows) - both_pass
        kick_rate = (kicked / len(rows)) if rows else 0.0

        # --- B0 枯竭预测（最关键的单店结论）---
        add("### B0 枯竭预测：这个店还能补几周（⚠️ 先看这个）")
        add("")
        add("> 公式：`耗尽周数 ≈ fresh ÷ (席位 × 踢出率)`。"
            "R4「被筛掉 = 已采集过 = 永不回补」⇒ `fresh` 是一次性资源。")
        add("")
        add("| 卖家 | 在售(可见) | 已采集过 | fresh | 预计耗尽 |")
        add("|------|-----------|---------|-------|---------|")
        for seller, seller_rows in sorted(by_seller.items(), key=lambda kv: -len(kv[1]))[:15]:
            captured = captured_by_seller.get(seller, 0)
            visible = len(fetch_discovered_ids(seller))
            pool = max(visible, len(seller_rows), captured)
            fresh = max(0, pool - captured)
            dry = weeks_until_dry(
                roster_size=pool,
                limit=limit,
                kick_rate=kick_rate,
            )
            dry_text = "永不枯竭" if dry is None else ("已枯竭" if dry <= 0 else f"{dry} 周")
            add(f"| `{seller}` | {pool} | {captured} | {fresh} | {dry_text} |")
        if len(by_seller) > 15:
            add(f"| ... | 另有 {len(by_seller) - 15} 家 | | | |")
        add("")

        # --- B1 fresh 池剩余 ---
        add("### B1 `fresh` 池剩余（还能补几个）")
        add("")
        add("| 卖家 | 本周有数据 | 已采集过 | 主页可见上限 | **fresh 剩余** |")
        add("|------|-----------|---------|-------------|---------------|")
        fresh_stats: list[tuple[str, int]] = []
        for seller, seller_rows in sorted(by_seller.items(), key=lambda kv: -len(kv[1])):
            captured = captured_by_seller.get(seller, 0)
            visible = len(fetch_discovered_ids(seller))
            visible_cap = max(visible, len(seller_rows), captured)
            fresh = max(0, visible_cap - captured)
            fresh_stats.append((seller, fresh))
            add(f"| `{seller}` | {len(seller_rows)} | {captured} | {visible_cap} | **{fresh}** |")
        if len(fresh_stats) > 12:
            add(f"| ... | 另有 {len(fresh_stats) - 12} 家 | | | |")
        total_fresh = sum(f for _, f in fresh_stats)
        dry_sellers = sum(1 for _, f in fresh_stats if f == 0)
        add("")
        add(f"- **fresh 总剩余：{total_fresh}** 个（{len(fresh_stats)} 家店）")
        add(f"- **池已干的店：{dry_sellers} 家**"
            f"{'（这些店席位只会减不会增）' if dry_sellers else ''}")
        add("")

        # --- B2 存量门槛分布 ---
        view_totals = [float(_as_int(r.get("view_end"))) for r in rows]
        quant = _quantiles(view_totals)
        passed_stock = sum(1 for v in view_totals if v >= min_view_total)
        add(f"### B2 存量门槛分布（`view_total ≥ {min_view_total}`）")
        add("")
        add("| 分位 | view_total |")
        add("|------|-----------|")
        for name, value in quant.items():
            add(f"| {name} | {_fmt(value)} |")
        add("")
        add(f"- 过存量门槛：**{passed_stock} / {len(rows)}**"
            f"（{passed_stock / len(rows) * 100:.1f}%）")
        add(f"- 被存量门槛挡下：**{len(rows) - passed_stock}** 个")
        add("")

        # --- B3/B6 双门槛判定 ---
        add("### B3/B6 双门槛判定与主导约束")
        add("")
        add(f"- 两门槛都过（保留）：**{both_pass}**（{both_pass / len(rows) * 100:.1f}%）")
        add(f"- 会被踢出：**{kicked}**（{kicked / len(rows) * 100:.1f}%）")
        add(f"  - 其中**存量不足**：{stock_fail} 个")
        add(f"  - 其中**增长不足**：{growth_fail} 个")
        add(f"  - 主导约束："
            f"{'**存量门槛**（保证有浏览量）' if stock_fail > growth_fail else '**增长门槛**（最近要有增长）'}"
            f"（{max(stock_fail, growth_fail)} vs {min(stock_fail, growth_fail)}）")
        add("")

        # --- B4 补位供需 ---
        add("### B4 补位供需对照")
        add("")
        add(f"- 需补位：**{kicked}** 个")
        add(f"- fresh 可用：**{total_fresh}** 个")
        if total_fresh >= kicked:
            add(f"- ✅ 供 ≥ 需，本轮可补满（消耗 {kicked}，剩余 {total_fresh - kicked}）")
        else:
            add(f"- ⚠️ **供 < 需**，缺口 **{kicked - total_fresh}** 个 → 席位将被空出")
        add("")

        # --- B5 收敛预测 ---
        per_seller_roster = max(len(rows), limit)
        timeline = simulate_convergence(
            roster_size=per_seller_roster,
            fresh_remaining=max(0, total_fresh // max(1, len(by_seller))),
            kick_rate=kick_rate,
            limit=limit,
            weeks=forecast_weeks,
        )
        add("### B5 收敛预测（单店均摊口径）")
        add("")
        add(f"- 本周踢出率：**{kick_rate * 100:.1f}%**")
        add("")
        add("| 周 | 在监控 | fresh 剩余 | 已用席位 | 空席 |")
        add("|----|--------|-----------|---------|------|")
        for point in timeline:
            add(f"| +{point['week']} | {point['active']} | {point['fresh']} "
                f"| {point['seats_used']} | {point['vacant']} |")
        add("")

        # --- B8 稳态可持续性（最关键的风险提示）---
        add("### B8 稳态可持续性（⚠️ 最关键）")
        add("")
        add("> 纯模型下席位会**几何衰减**：每轮踢出 k% 但补不满，剩下的一直在缩。")
        add("> 席位规模**完全依赖 `fresh` 供给**。池子干了之后，席位只会继续降。")
        add("")
        weekly_need = required_fresh_per_week(
            limit=limit, kick_rate=kick_rate, target_seats=limit
        )
        add(f"- 本周踢出率 **{kick_rate * 100:.1f}%** → 维持满 {limit} 席，"
            f"**每周需补 {weekly_need} 个 fresh**")
        add("")
        add("| 店铺商品总量 | 可维持周数 | 一年内可持续？ |")
        add("|-------------|-----------|---------------|")
        for pool_size in (100, 200, 300, 500, 1000, 2000):
            budget = fresh_budget_for_steady_state(
                limit=limit, kick_rate=kick_rate,
                target_seats=limit, pool_size=pool_size,
            )
            if budget["weekly_need"] <= 0:
                weeks = "∞"
                mark = "✅"
            elif budget["weeks_until_dry"] <= 0:
                weeks = "0（已干）"
                mark = "❌"
            else:
                weeks = str(budget["weeks_until_dry"])
                mark = "✅" if budget["sustainable"] else "❌"
            add(f"| {pool_size} | {weeks} 周 | {mark} |")
        add("")
        add(f"**结论**："
            f"{'当前踢出率下，即使 2000 个商品的店铺也只能撑约 ' + str(fresh_budget_for_steady_state(limit=limit, kick_rate=kick_rate, target_seats=limit, pool_size=2000)['weeks_until_dry']) + ' 周。**这个模型不可长期持续，需要引入回炉机制。**' if kick_rate > 0.02 else '踢出率很低，模型可长期持续。'}")
        add("")

        # --- B7 口径校验 ---
        alt_kick = sum(
            1 for r in rows
            if _as_int(r.get("view_growth")) < min_view_total
            and _as_int(r.get("want_growth")) < min_want_growth
        )
        add("### B7 口径校验（存量 vs 增长）")
        add("")
        add(f"- 当前口径（**存量 {min_view_total} + 增长 {min_view_growth}/{min_want_growth}**）"
            f"→ 踢出 **{kicked}** 个")
        add(f"- 若把 `{min_view_total}` 理解为**周增长**阈值 → 踢出 **{alt_kick}** 个")
        add(f"- 差异：**{abs(kicked - alt_kick)}** 个"
            f"（{'✅ 两种理解接近' if abs(kicked - alt_kick) <= max(3, len(rows) * 0.05) else '⚠️ 口径影响很大，必须确认'}）")
        add("")

    # --- 结论 ---
    add("## 结论与建议")
    add("")
    add("**这个模型是单调收敛的 —— 席位只会减少，不会增加。**")
    add("")
    add("1. 每轮踢出 + 补位，`fresh` 池只减不增（R4：被筛掉 = 已采集过，永不回补）")
    add("2. `fresh` 一旦耗尽，席位就以踢出率的速度**指数衰减**")
    add("3. 因此「店铺固定采 100 个」只在**初期**成立，之后必然降到稳态")
    add("")
    add("**已定稿的配置**：")
    add("")
    add(f"- 增量阈值 = **{min_view_growth}**（决策 1）")
    add("- 枯竭路线 = **A：席位置空就置空，不为凑数采烂商品**（决策 2）")
    add("")
    add("> 路线 A 的含义：`fresh` 不够时，**席位空着就空着**。"
        "空席不是故障，而是「这个店已没有更多好货」的信号。")
    add("> 红线：**绝不为凑满席位而降低门槛、或把被踢的拉回来。**")
    add("")
    add("**上线前必须做的动作**：")
    add("")
    add("| 优先级 | 动作 | 依据 |")
    add("|--------|------|------|")
    add("| P0 | 用本报告 B0/B8 拿到**真实踢出率** → 算出实际枯竭周数 | B0、B8 |")
    add("| P0 | 若 B1/B4 显示 fresh 不够 → 放大 `CANDIDATE_POOL_FACTOR`（同时 `max_items`） | B1、B4 |")
    add("| P1 | 若席位掉得比预期狠（3 个月内 < 30）→ 再评估路线 C | B8 |")
    add("")
    add("**路线 A 已采纳；B / C 为日后备选**（详见设计文档 §3）：")
    add("")
    add("- ✅ **路线 A（当前）**：席位置空，不为凑数采烂商品 —— 这正是「看到最后剩下的采集数据」")
    add("- ⬜ **路线 B**：踢出满 8 周回炉，给第二次机会（违反 R4，但能长期维持 100 席）")
    add("- ⬜ **路线 C**：只让「存量高、只是增长差」的回炉（精准，不浪费在真冷门）")
    add("")
    add("> 本报告全程只读（仅 SELECT），未修改任何数据。")
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="店铺「保量 + 补位」选品模拟（只读）")
    parser.add_argument("--weeks", type=int, default=4, help="评估最近 N 个完整自然周（默认 4）")
    parser.add_argument("--limit", type=int, default=100, help="每店席位（默认 100）")
    parser.add_argument("--min-view-total", type=int, default=100, help="存量门槛：浏览量下限（默认 100）")
    parser.add_argument("--min-view-growth", type=int, default=20, help="增量门槛：浏览增长下限（默认 20，已定稿）")
    parser.add_argument("--min-want-growth", type=int, default=2, help="增量门槛：想要增长下限（默认 2）")
    parser.add_argument("--pool-factor", type=int, default=2, help="候选池放大倍数（默认 2）")
    parser.add_argument("--forecast-weeks", type=int, default=8, help="收敛预测周数（默认 8）")
    parser.add_argument("--out", type=str, default="", help="输出 markdown 路径（默认仅打印）")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not os.getenv("DATABASE_URL"):
        print("[中止] 未配置 DATABASE_URL，无法读取数据。")
        print("       请在仓库根目录的 .env 中设置 DATABASE_URL 后重试。")
        return 2

    try:
        report = build_report(
            max(1, args.weeks),
            limit=max(1, args.limit),
            min_view_total=max(0, args.min_view_total),
            min_view_growth=max(0, args.min_view_growth),
            min_want_growth=max(0, args.min_want_growth),
            pool_factor=max(1, args.pool_factor),
            forecast_weeks=max(1, args.forecast_weeks),
        )
    except Exception as exc:
        print(f"[中止] 生成报告失败：{exc}")
        return 1

    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(report)
        print(f"\n[已写入] {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

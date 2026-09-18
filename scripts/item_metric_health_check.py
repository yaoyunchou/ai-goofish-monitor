"""卖家订阅商品「浏览/想要」周增长体检（只读）。

用途：在实现「一周无增长 → 自动停止监控」之前，先摸清数据底子。
本脚本 **只读**，不执行任何 INSERT / UPDATE / DELETE / DDL。

产出：
  - 控制台人可读摘要
  - reports/item_metric_health_<date>.md 报告

用法：
    python -m scripts.item_metric_health_check
    python -m scripts.item_metric_health_check --week-start 2026-09-07 --week-end 2026-09-13
    python -m scripts.item_metric_health_check --keep-view 10 --keep-want 2
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.infrastructure.persistence.db_connection import db_connection  # noqa: E402
from src.infrastructure.persistence.storage_bootstrap import bootstrap_storage  # noqa: E402
from src.time_utils import SHANGHAI_TZ, shanghai_today  # noqa: E402

DEFAULT_KEEP_VIEW = int(os.getenv("MONITOR_KEEP_VIEW_GROWTH", "10"))
DEFAULT_KEEP_WANT = int(os.getenv("MONITOR_KEEP_WANT_GROWTH", "2"))
DEFAULT_MIN_DAYS = int(os.getenv("MONITOR_MIN_DAYS_WITH_DATA", "2"))
DEFAULT_PROTECT_DAYS = int(os.getenv("MONITOR_PROTECT_DAYS", "14"))

BAR_CHARS = "▁▂▃▄▅▆▇█"


# --------------------------------------------------------------------------
# 周界计算
# --------------------------------------------------------------------------
def last_full_week(today: date | None = None) -> tuple[date, date]:
    """返回上一个完整自然周（周一 ~ 周日，Asia/Shanghai）。

    若今天就是周一，则返回「上周」（周一不能代表本周完整）。
    """
    current = today or shanghai_today()
    # current.weekday(): 周一=0
    this_monday = current - timedelta(days=current.weekday())
    last_monday = this_monday - timedelta(days=7)
    return last_monday, last_monday + timedelta(days=6)


def parse_week(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


# --------------------------------------------------------------------------
# 各体检项
# --------------------------------------------------------------------------
def check_overview(conn) -> dict:
    """T1：总量与时间跨度。"""
    row = conn.execute(
        """
        SELECT COUNT(*)                        AS total_rows,
               COUNT(DISTINCT item_id)         AS distinct_items,
               COUNT(DISTINCT seller_user_id)  AS distinct_sellers,
               COUNT(DISTINCT snapshot_day)    AS distinct_days,
               MIN(snapshot_day)               AS min_day,
               MAX(snapshot_day)               AS max_day
        FROM seller_item_daily_metrics
        """
    ).fetchone()
    return dict(row) if row else {}


def check_null_quality(conn) -> dict:
    """T2：want/view 的 NULL 率与 0 值率。"""
    row = conn.execute(
        """
        SELECT COUNT(*)                                  AS total_rows,
               COUNT(*) FILTER (WHERE want_count IS NULL) AS want_null,
               COUNT(*) FILTER (WHERE view_count IS NULL) AS view_null,
               COUNT(*) FILTER (WHERE want_count = 0)     AS want_zero,
               COUNT(*) FILTER (WHERE view_count = 0)     AS view_zero
        FROM seller_item_daily_metrics
        """
    ).fetchone()
    return dict(row) if row else {}


def check_days_distribution(conn, week_start: date, week_end: date) -> Counter:
    """T3：窗口内每个商品的「有数据天数」分布。"""
    rows = conn.execute(
        """
        SELECT days_with_data, COUNT(*) AS items
        FROM (
            SELECT seller_user_id, item_id, COUNT(*) AS days_with_data
            FROM seller_item_daily_metrics
            WHERE snapshot_day BETWEEN ? AND ?
            GROUP BY seller_user_id, item_id
        ) t
        GROUP BY days_with_data
        ORDER BY days_with_data
        """,
        (week_start.isoformat(), week_end.isoformat()),
    ).fetchall()
    return Counter({int(r["days_with_data"]): int(r["items"]) for r in rows})


def fetch_week_growth(conn, week_start: date, week_end: date) -> list[dict]:
    """T4-T8 的基础数据：窗口内每个商品的首末指标 + 跨度信息。"""
    rows = conn.execute(
        """
        WITH first_seen AS (
            SELECT DISTINCT ON (seller_user_id, item_id)
                   seller_user_id, item_id, snapshot_day,
                   view_count, want_count
            FROM seller_item_daily_metrics
            WHERE snapshot_day BETWEEN ? AND ?
            ORDER BY seller_user_id, item_id, snapshot_day ASC, captured_at ASC
        ),
        last_seen AS (
            SELECT DISTINCT ON (seller_user_id, item_id)
                   seller_user_id, item_id, snapshot_day,
                   view_count, want_count
            FROM seller_item_daily_metrics
            WHERE snapshot_day BETWEEN ? AND ?
            ORDER BY seller_user_id, item_id, snapshot_day DESC, captured_at DESC
        ),
        span AS (
            SELECT seller_user_id, item_id,
                   COUNT(*)          AS days_with_data,
                   MIN(snapshot_day) AS first_day,
                   MAX(snapshot_day) AS last_day
            FROM seller_item_daily_metrics
            WHERE snapshot_day BETWEEN ? AND ?
            GROUP BY seller_user_id, item_id
        )
        SELECT f.seller_user_id,
               f.item_id,
               s.days_with_data,
               s.first_day,
               s.last_day,
               f.view_count AS view_start,
               l.view_count AS view_end,
               COALESCE(l.view_count, 0) - COALESCE(f.view_count, 0) AS view_growth,
               f.want_count AS want_start,
               l.want_count AS want_end,
               COALESCE(l.want_count, 0) - COALESCE(f.want_count, 0) AS want_growth,
               i.title,
               i.item_status,
               i.first_seen_at
        FROM first_seen f
        JOIN last_seen l USING (seller_user_id, item_id)
        JOIN span      s USING (seller_user_id, item_id)
        LEFT JOIN seller_subscription_items i
               ON i.seller_user_id = f.seller_user_id
              AND i.item_id = f.item_id
        ORDER BY f.seller_user_id, f.item_id
        """,
        (
            week_start.isoformat(),
            week_end.isoformat(),
            week_start.isoformat(),
            week_end.isoformat(),
            week_start.isoformat(),
            week_end.isoformat(),
        ),
    ).fetchall()
    return [dict(r) for r in rows]


def histogram(values: list[int], buckets: list[tuple[str, int, int]]) -> list[tuple[str, int]]:
    """按给定区间统计频次。buckets = [(label, low, high)]，high=None 表示上不封顶。"""
    out: list[tuple[str, int]] = []
    for label, low, high in buckets:
        if high is None:
            count = sum(1 for v in values if v >= low)
        else:
            count = sum(1 for v in values if low <= v <= high)
        out.append((label, count))
    return out


def sparkline(counts: list[int]) -> str:
    if not counts:
        return ""
    peak = max(counts) or 1
    return "".join(BAR_CHARS[min(len(BAR_CHARS) - 1, c * (len(BAR_CHARS) - 1) // peak)] for c in counts)


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------
def build_report(
    *,
    week_start: date,
    week_end: date,
    keep_view: int,
    keep_want: int,
    min_days: int,
    protect_days: int,
) -> tuple[str, dict]:
    bootstrap_storage()
    with db_connection() as conn:
        overview = check_overview(conn)
        quality = check_null_quality(conn)
        days_dist = check_days_distribution(conn, week_start, week_end)
        growth_rows = fetch_week_growth(conn, week_start, week_end)

    lines: list[str] = []
    add = lines.append

    add("# 卖家订阅商品「浏览/想要」周增长体检报告")
    add("")
    add(f"- 生成时间：{datetime.now(tz=SHANGHAI_TZ).isoformat(timespec='seconds')}")
    add(f"- 判定窗口：**{week_start} ~ {week_end}**（上一完整自然周，Asia/Shanghai）")
    add(f"- 假设阈值：保留条件 = 浏览增长 ≥ {keep_view} **或** 想要增长 ≥ {keep_want}")
    add(f"- 数据下限：窗口内 ≥ {min_days} 天有数据才参与判定；新商品宽限 {protect_days} 天")
    add("")

    # ---- T1 ----
    add("## T1 数据总览")
    add("")
    add("| 指标 | 值 |")
    add("|---|---|")
    add(f"| 日指标总行数 | {overview.get('total_rows', 0):,} |")
    add(f"| 去重商品数 | {overview.get('distinct_items', 0):,} |")
    add(f"| 去重卖家数 | {overview.get('distinct_sellers', 0):,} |")
    add(f"| 覆盖自然日数 | {overview.get('distinct_days', 0):,} |")
    add(f"| 日期范围 | {overview.get('min_day')} ~ {overview.get('max_day')} |")
    add("")
    if not overview.get("total_rows"):
        add("> ⚠️ **表内无数据**，无法进行任何判定。请先确认卖家订阅采集是否正常运行。")
        return "\n".join(lines), {"fatal": "empty_table"}

    # ---- T2 ----
    total = quality.get("total_rows", 0) or 1
    add("## T2 数据质量（want_count / view_count）")
    add("")
    add("| 检查 | 数量 | 占比 |")
    add("|---|---|---|")
    add(f"| want_count 为 NULL | {quality.get('want_null', 0):,} | {quality.get('want_null', 0) / total:.2%} |")
    add(f"| view_count 为 NULL | {quality.get('view_null', 0):,} | {quality.get('view_null', 0) / total:.2%} |")
    add(f"| want_count = 0 | {quality.get('want_zero', 0):,} | {quality.get('want_zero', 0) / total:.2%} |")
    add(f"| view_count = 0 | {quality.get('view_zero', 0):,} | {quality.get('view_zero', 0) / total:.2%} |")
    add("")
    null_rate = (quality.get("want_null", 0) + quality.get("view_null", 0)) / (total * 2)
    if null_rate > 0.05:
        add(f"> ⚠️ NULL 率 {null_rate:.2%} 偏高。采集侧 `has_want_and_view()` 本应拦截空值，"
            f"说明存在更早版本写入的历史数据。判定逻辑需要能容忍 NULL。")
    else:
        add(f"> ✅ NULL 率 {null_rate:.2%}，数据质量良好，判定可以放心依赖这两个字段。")
    add("")

    # ---- T3 ----
    add("## T3 窗口内「有数据天数」分布")
    add("")
    add("| 天数 | 商品数 | 占比 |")
    add("|---|---|---|")
    total_items = sum(days_dist.values()) or 1
    for day in sorted(days_dist):
        count = days_dist[day]
        add(f"| {day} 天 | {count:,} | {count / total_items:.1%} |")
    add("")
    judged = sum(c for d, c in days_dist.items() if d >= min_days)
    add(f"- 窗口内出现过的商品：**{sum(days_dist.values()):,}**")
    add(f"- 满足「≥ {min_days} 天有数据」可参与判定：**{judged:,}**"
        f"（占 {judged / total_items:.1%}）")
    add(f"- 仅 1 天数据、无法算增长（将被跳过）：**{days_dist.get(1, 0):,}**")
    add("")

    # ---- 面向可判定集合的统计 ----
    judged_rows = [
        r
        for r in growth_rows
        if int(r["days_with_data"]) >= min_days
        and r["view_start"] is not None
        and r["view_end"] is not None
    ]
    add("## T4 周增长分布（仅可判定商品）")
    add("")
    if not judged_rows:
        add("> ⚠️ 没有任何商品满足判定条件，无法校准阈值。")
        return "\n".join(lines), {"fatal": "no_judgeable_items"}

    view_growths = [int(r["view_growth"]) for r in judged_rows]
    want_growths = [int(r["want_growth"]) for r in judged_rows]

    view_buckets = [
        ("负增长（浏览量下降）", -10**9, -1),
        ("0（完全无增长）", 0, 0),
        ("1 - 9", 1, 9),
        (f"≥ {keep_view}（达标）", keep_view, None),
    ]
    want_buckets = [
        ("负增长", -10**9, -1),
        ("0（完全无增长）", 0, 0),
        (f"1 - {max(keep_want - 1, 1)}", 1, max(keep_want - 1, 1)),
        (f"≥ {keep_want}（达标）", keep_want, None),
    ]
    add("### 浏览增长（view_growth）")
    add("")
    add("| 区间 | 商品数 | 占比 |")
    add("|---|---|---|")
    for label, count in histogram(view_growths, view_buckets):
        add(f"| {label} | {count:,} | {count / len(judged_rows):.1%} |")
    add("")
    add("### 想要增长（want_growth）")
    add("")
    add("| 区间 | 商品数 | 占比 |")
    add("|---|---|---|")
    for label, count in histogram(want_growths, want_buckets):
        add(f"| {label} | {count:,} | {count / len(judged_rows):.1%} |")
    add("")
    add(f"- 浏览增长中位数：**{median(view_growths)}**，均值：**{mean(view_growths):.1f}**")
    add(f"- 想要增长中位数：**{median(want_growths)}**，均值：**{mean(want_growths):.1f}**")
    add("")

    # ---- T5 ----
    add("## T5 按当前阈值会停掉多少？（OR 口径）")
    add("")
    muted = [
        r
        for r in judged_rows
        if int(r["view_growth"]) < keep_view and int(r["want_growth"]) < keep_want
    ]
    kept = len(judged_rows) - len(muted)
    add(f"- 判定集合：**{len(judged_rows):,}** 个商品")
    add(f"- ✅ 保留（任一达标）：**{kept:,}**（{kept / len(judged_rows):.1%}）")
    add(f"- ⛔ 会被停用（两者都低）：**{len(muted):,}**（{len(muted) / len(judged_rows):.1%}）")
    add("")
    if len(muted) / len(judged_rows) > 0.6:
        add("> ⚠️ 停用比例超过 60%，阈值偏激进，建议调低 "
            f"`MONITOR_KEEP_VIEW_GROWTH`（当前 {keep_view}）。")
    elif len(muted) == 0:
        add("> ✅ 当前阈值下没有商品会被停用，可以考虑调高阈值或改用更严格的周期。")
    else:
        add("> ✅ 停用比例看起来合理，可进入影子模式验证。")
    add("")

    add("### 阈值敏感度（浏览阈值扫描）")
    add("")
    add("| 浏览阈值 | 想要阈值 | 会停用商品数 | 占比 |")
    add("|---|---|---|---|")
    for v in [0, 1, 3, 5, 10, 20, 50]:
        n = sum(
            1
            for r in judged_rows
            if int(r["view_growth"]) < v and int(r["want_growth"]) < keep_want
        )
        add(f"| {v} | {keep_want} | {n:,} | {n / len(judged_rows):.1%} |")
    add("")

    # ---- T6 ----
    add("## T6 数据中断商品（疑似已售 / 已停采）")
    add("")
    interrupted = [
        r for r in growth_rows if r["last_day"] != week_end
    ]
    add(f"- 窗口末日（{week_end}）无数据的商品：**{len(interrupted):,}**"
        f"（占窗口内出现过商品的 {len(interrupted) / max(len(growth_rows), 1):.1%}）")
    add(f"- 这些商品会被标记 `interrupted` 并 **跳过判定**，避免把「卖掉了」误判成「凉了」。")
    add("")
    sold = [r for r in growth_rows if (r.get("item_status") or "") not in ("", "在售")]
    if sold:
        add(f"- 其中 `item_status != '在售'` 的：**{len(sold):,}**")
        add("")

    # ---- T7 ----
    add("## T7 异常数据：周增长为负")
    add("")
    neg_view = [r for r in judged_rows if int(r["view_growth"]) < 0]
    neg_want = [r for r in judged_rows if int(r["want_growth"]) < 0]
    add(f"- 浏览量下降的商品：**{len(neg_view):,}**")
    add(f"- 想要数下降的商品：**{len(neg_want):,}**")
    add("")
    if neg_view or neg_want:
        add("> ℹ️ 闲鱼侧计数下降通常是删差评/合并 SKU/口径调整所致。属于正常噪声，"
            "判定用 `<` 比较天然兼容，无需特殊处理。")
    add("")

    # ---- T8 ----
    add("## T8 按卖家汇总（不达标商品最多的 Top 15）")
    add("")
    per_seller: Counter = Counter()
    per_seller_total: Counter = Counter()
    for r in judged_rows:
        per_seller_total[r["seller_user_id"]] += 1
    for r in muted:
        per_seller[r["seller_user_id"]] += 1
    add("| 卖家 | 不达标商品 | 可判定商品 | 占比 |")
    add("|---|---|---|---|")
    for seller_id, bad in per_seller.most_common(15):
        t = per_seller_total[seller_id]
        add(f"| {seller_id} | {bad:,} | {t:,} | {bad / t:.0%} |")
    if not per_seller:
        add("| （无不达标商品） | 0 | - | - |")
    add("")

    # ---- 样例 ----
    add("## 附：会被停用的商品样例（前 20 条）")
    add("")
    add("| 卖家 | 商品 | 数据天数 | 浏览 起→止（增长） | 想要 起→止（增长） |")
    add("|---|---|---|---|---|")
    muted_sorted = sorted(
        muted,
        key=lambda r: (int(r["view_growth"]), int(r["want_growth"])),
    )
    for r in muted_sorted[:20]:
        title = (r.get("title") or "(无标题)")[:28]
        add(
            f"| {r['seller_user_id']} | {title} | {r['days_with_data']} "
            f"| {r['view_start']}→{r['view_end']} (+{r['view_growth']}) "
            f"| {r['want_start']}→{r['want_end']} (+{r['want_growth']}) |"
        )
    if not muted_sorted:
        add("| - | （无） | - | - | - |")
    add("")

    summary = {
        "total_rows": overview.get("total_rows", 0),
        "total_items_in_window": sum(days_dist.values()),
        "judgeable_items": len(judged_rows),
        "would_mute": len(muted),
        "would_keep": kept,
        "interrupted": len(interrupted),
    }
    return "\n".join(lines), summary


def median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def mean(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="卖家订阅商品周增长体检（只读）")
    parser.add_argument("--week-start", help="窗口起始日 YYYY-MM-DD（默认：上一完整周的周一）")
    parser.add_argument("--week-end", help="窗口结束日 YYYY-MM-DD（默认：上一完整周的周日）")
    parser.add_argument("--keep-view", type=int, default=DEFAULT_KEEP_VIEW,
                        help=f"浏览增长达标线，默认 {DEFAULT_KEEP_VIEW}")
    parser.add_argument("--keep-want", type=int, default=DEFAULT_KEEP_WANT,
                        help=f"想要增长达标线，默认 {DEFAULT_KEEP_WANT}")
    parser.add_argument("--min-days", type=int, default=DEFAULT_MIN_DAYS,
                        help=f"窗口内最少有数据天数，默认 {DEFAULT_MIN_DAYS}")
    parser.add_argument("--protect-days", type=int, default=DEFAULT_PROTECT_DAYS,
                        help=f"新商品宽限天数，默认 {DEFAULT_PROTECT_DAYS}")
    parser.add_argument("--out", help="报告输出路径（默认 reports/item_metric_health_<date>.md）")
    args = parser.parse_args()

    if args.week_start or args.week_end:
        if not (args.week_start and args.week_end):
            parser.error("--week-start 与 --week-end 必须同时提供")
        week_start = parse_week(args.week_start)
        week_end = parse_week(args.week_end)
        if week_end < week_start:
            parser.error("--week-end 不能早于 --week-start")
    else:
        week_start, week_end = last_full_week()

    print(f"[体检] 判定窗口 {week_start} ~ {week_end}")
    print(f"[体检] 阈值：保留 = 浏览增长 ≥ {args.keep_view} 或 想要增长 ≥ {args.keep_want}")
    print()

    report, summary = build_report(
        week_start=week_start,
        week_end=week_end,
        keep_view=args.keep_view,
        keep_want=args.keep_want,
        min_days=args.min_days,
        protect_days=args.protect_days,
    )

    out_path = Path(args.out) if args.out else Path("reports") / f"item_metric_health_{week_start}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    if "fatal" in summary:
        print(f"[体检] 中止：{summary['fatal']}")
        print(f"[体检] 报告已写入 {out_path}")
        return 1

    print("── 摘要 ──────────────────────────────")
    print(f"  日指标总行数        : {summary['total_rows']:,}")
    print(f"  窗口内出现过商品    : {summary['total_items_in_window']:,}")
    print(f"  可判定商品          : {summary['judgeable_items']:,}")
    print(f"  其中会被停用        : {summary['would_mute']:,}")
    print(f"  其中保留            : {summary['would_keep']:,}")
    print(f"  数据中断（跳过）    : {summary['interrupted']:,}")
    print("──────────────────────────────────────")
    print(f"[体检] 完整报告：{out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""商品级监控健康度判定：一周浏览/想要无增长 → 自动停止监控。

判定周期：Asia/Shanghai 自然周（周一 ~ 周日）。
判定粒度：单个商品（seller_user_id + item_id）。

设计要点（防误杀）：
  1. 窗口内数据不足 MIN_DAYS_WITH_DATA 天 → 跳过（无法算增长）。
  2. 数据中断（窗口末日无数据）→ 判定 interrupted，不停用（疑似已售/已下架）。
  3. 新商品宽限期 PROTECT_DAYS 内 → 跳过。
  4. DRY_RUN 影子模式 → 只记录与通知，不落地 is_muted。
  5. MAX_MUTE_PER_WEEK 熔断上限 → 单周最多停用 N 个，防止阈值失效批量误杀。
  6. 判定结果全部落库，可审计、可恢复。
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from src.infrastructure.persistence.db_connection import db_connection
from src.infrastructure.persistence.storage_bootstrap import bootstrap_storage
from src.services.seller_item_daily_storage import (
    mute_items_sync,
    shanghai_now_iso,
    weekly_item_growth_sync,
)
from src.time_utils import SHANGHAI_TZ, shanghai_today

# 判定动作
ACTION_KEPT = "kept"
ACTION_MUTED = "muted"
ACTION_DRY_RUN = "dry_run"
ACTION_SKIPPED = "skipped"
ACTION_INTERRUPTED = "interrupted"

# 跳过原因
SKIP_NO_METRIC_DATA = "首末指标缺失，无法计算增长"
SKIP_ALREADY_MUTED = "此前已停止监控"
SKIP_PROTECTED = "新商品宽限期内"
SKIP_TOO_FEW_DAYS = "窗口内有数据天数不足"


def _as_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", ""}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


@dataclass(frozen=True)
class MonitorConfig:
    """判定阈值，全部来自环境变量，便于按周校准。"""

    auto_disable_enabled: bool = False
    dry_run: bool = True
    keep_view_growth: int = 10
    keep_want_growth: int = 2
    min_days_with_data: int = 2
    protect_days: int = 14
    max_mute_per_week: int = 0  # 0 = 不限

    @classmethod
    def from_env(cls) -> "MonitorConfig":
        return cls(
            auto_disable_enabled=_as_bool(os.getenv("MONITOR_AUTO_DISABLE_ENABLED"), False),
            dry_run=_as_bool(os.getenv("MONITOR_DRY_RUN"), True),
            keep_view_growth=_as_int(os.getenv("MONITOR_KEEP_VIEW_GROWTH"), 10),
            keep_want_growth=_as_int(os.getenv("MONITOR_KEEP_WANT_GROWTH"), 2),
            min_days_with_data=max(2, _as_int(os.getenv("MONITOR_MIN_DAYS_WITH_DATA"), 2)),
            protect_days=max(0, _as_int(os.getenv("MONITOR_PROTECT_DAYS"), 14)),
            max_mute_per_week=max(0, _as_int(os.getenv("MONITOR_MAX_MUTE_PER_WEEK"), 0)),
        )


@dataclass
class ItemHealthDecision:
    seller_user_id: str
    item_id: str
    title: str | None
    week_start: date
    week_end: date
    days_with_data: int = 0
    view_start: int | None = None
    view_end: int | None = None
    view_growth: int = 0
    want_start: int | None = None
    want_end: int | None = None
    want_growth: int = 0
    healthy: bool = True
    reason: str = ""
    action: str = ACTION_KEPT
    price: str | None = None
    item_link: str | None = None

    def to_row(self) -> dict[str, Any]:
        return {
            "week_start": self.week_start.isoformat(),
            "week_end": self.week_end.isoformat(),
            "seller_user_id": self.seller_user_id,
            "item_id": self.item_id,
            "title": self.title,
            "days_with_data": self.days_with_data,
            "view_start": self.view_start,
            "view_end": self.view_end,
            "view_growth": self.view_growth,
            "want_start": self.want_start,
            "want_end": self.want_end,
            "want_growth": self.want_growth,
            "healthy": self.healthy,
            "reason": self.reason,
            "action": self.action,
        }


# ---------------------------------------------------------------------------
# 周界
# ---------------------------------------------------------------------------
def last_full_week(today: date | None = None) -> tuple[date, date]:
    """上一个完整自然周（周一 ~ 周日，Asia/Shanghai）。周一当天取上一周。"""
    current = today or shanghai_today()
    this_monday = current - timedelta(days=current.weekday())
    last_monday = this_monday - timedelta(days=7)
    return last_monday, last_monday + timedelta(days=6)


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return datetime.strptime(text[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
    return None


# ---------------------------------------------------------------------------
# 判定
# ---------------------------------------------------------------------------
def evaluate_week(
    week_start: date,
    week_end: date,
    *,
    config: MonitorConfig | None = None,
    rows: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> list[ItemHealthDecision]:
    """对窗口内每个商品给出健康度判定（不含实际停用）。"""
    cfg = config or MonitorConfig.from_env()
    data = rows if rows is not None else weekly_item_growth_sync(week_start, week_end)
    current = now or datetime.now(tz=SHANGHAI_TZ)
    today = current.astimezone(SHANGHAI_TZ).date()
    protect_cutoff = today - timedelta(days=cfg.protect_days)

    decisions: list[ItemHealthDecision] = []
    for row in data:
        decision = ItemHealthDecision(
            seller_user_id=str(row.get("seller_user_id") or ""),
            item_id=str(row.get("item_id") or ""),
            title=row.get("title"),
            week_start=week_start,
            week_end=week_end,
            days_with_data=int(row.get("days_with_data") or 0),
            view_start=row.get("view_start"),
            view_end=row.get("view_end"),
            view_growth=int(row.get("view_growth") or 0),
            want_start=row.get("want_start"),
            want_end=row.get("want_end"),
            want_growth=int(row.get("want_growth") or 0),
            price=str(row["price"]) if row.get("price") is not None else None,
            item_link=row.get("item_link"),
        )

        # --- 硬性跳过条件（顺序即优先级） ---
        if decision.days_with_data < cfg.min_days_with_data:
            decision.action = ACTION_SKIPPED
            decision.reason = f"{SKIP_TOO_FEW_DAYS}（{decision.days_with_data} < {cfg.min_days_with_data}）"
            decisions.append(decision)
            continue

        if row.get("is_muted"):
            decision.action = ACTION_SKIPPED
            decision.reason = SKIP_ALREADY_MUTED
            decisions.append(decision)
            continue

        if not row.get("has_metric_data", True):
            decision.action = ACTION_SKIPPED
            decision.reason = SKIP_NO_METRIC_DATA
            decisions.append(decision)
            continue

        # 数据中断：窗口末日无数据 → 疑似已售/已下架，不能判为「凉了」
        last_day = _parse_date(row.get("last_day"))
        if last_day is not None and last_day < week_end:
            decision.action = ACTION_INTERRUPTED
            decision.reason = f"数据在 {last_day} 中断（早于窗口末日 {week_end}），疑似已售或已下架"
            decisions.append(decision)
            continue

        # 新商品宽限期
        first_seen = _parse_date(row.get("first_seen_at"))
        if first_seen is not None and first_seen > protect_cutoff:
            decision.action = ACTION_SKIPPED
            decision.reason = f"{SKIP_PROTECTED}（首次采集 {first_seen}，宽限 {cfg.protect_days} 天）"
            decisions.append(decision)
            continue

        # --- OR 口径：任一达标即保留 ---
        view_ok = decision.view_growth >= cfg.keep_view_growth
        want_ok = decision.want_growth >= cfg.keep_want_growth
        if view_ok or want_ok:
            decision.healthy = True
            decision.action = ACTION_KEPT
            hits = []
            if view_ok:
                hits.append(f"浏览 +{decision.view_growth} ≥ {cfg.keep_view_growth}")
            if want_ok:
                hits.append(f"想要 +{decision.want_growth} ≥ {cfg.keep_want_growth}")
            decision.reason = "达标：" + "，".join(hits)
        else:
            decision.healthy = False
            decision.action = ACTION_DRY_RUN if cfg.dry_run else ACTION_MUTED
            decision.reason = (
                f"浏览 +{decision.view_growth} < {cfg.keep_view_growth} "
                f"且 想要 +{decision.want_growth} < {cfg.keep_want_growth}"
            )
        decisions.append(decision)

    return decisions


# ---------------------------------------------------------------------------
# 落库
# ---------------------------------------------------------------------------
def _persist_decisions_sync(decisions: Iterable[ItemHealthDecision]) -> int:
    rows = [d.to_row() for d in decisions]
    if not rows:
        return 0
    bootstrap_storage()
    with db_connection() as conn:
        for row in rows:
            conn.execute(
                """
                INSERT INTO item_monitor_health_weekly (
                    week_start, week_end, seller_user_id, item_id, title,
                    days_with_data, view_start, view_end, view_growth,
                    want_start, want_end, want_growth,
                    healthy, reason, action
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (week_start, seller_user_id, item_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    days_with_data = EXCLUDED.days_with_data,
                    view_start = EXCLUDED.view_start,
                    view_end = EXCLUDED.view_end,
                    view_growth = EXCLUDED.view_growth,
                    want_start = EXCLUDED.want_start,
                    want_end = EXCLUDED.want_end,
                    want_growth = EXCLUDED.want_growth,
                    healthy = EXCLUDED.healthy,
                    reason = EXCLUDED.reason,
                    action = EXCLUDED.action
                """,
                (
                    row["week_start"],
                    row["week_end"],
                    row["seller_user_id"],
                    row["item_id"],
                    row["title"],
                    row["days_with_data"],
                    row["view_start"],
                    row["view_end"],
                    row["view_growth"],
                    row["want_start"],
                    row["want_end"],
                    row["want_growth"],
                    row["healthy"],
                    row["reason"],
                    row["action"],
                ),
            )
        conn.commit()
    return len(rows)


def persist_decisions_sync(decisions: Iterable[ItemHealthDecision]) -> int:
    return _persist_decisions_sync(decisions)


# ---------------------------------------------------------------------------
# 通知文案
# ---------------------------------------------------------------------------
def build_notification_payload(
    muted: list[ItemHealthDecision],
    *,
    week_start: date,
    week_end: date,
    dry_run: bool,
    limit: int = 10,
) -> dict[str, str]:
    """组装成通知客户端可消费的商品形状 payload。"""
    verb = "【试运行】将停止监控" if dry_run else "已停止监控"
    title = f"[MONITOR] {verb} {len(muted)} 个低效商品（{week_start} ~ {week_end}）"

    lines: list[str] = []
    for index, decision in enumerate(muted[:limit], start=1):
        name = (decision.title or "(无标题)")[:32]
        price_part = f"（¥{decision.price}）" if decision.price else ""
        lines.append(
            f"{index}. {name}{price_part}\n"
            f"   卖家 {decision.seller_user_id}｜周浏览 +{decision.view_growth}"
            f"｜周想要 +{decision.want_growth}｜有数据 {decision.days_with_data} 天"
        )
    if len(muted) > limit:
        lines.append(f"...另有 {len(muted) - limit} 个，详见监控健康度页面")

    content_lines = [
        f"判定窗口: {week_start} ~ {week_end}",
        f"停用原因: 周浏览增长与周想要增长均未达标（两者都低才停）",
        "",
        *lines,
    ]
    return {
        "商品标题": title,
        "当前售价": "",
        "商品链接": "",
        "data_content": "\n".join(content_lines),
    }


async def _send_notification(payload: dict[str, str], reason: str) -> dict:
    try:
        from src.ai_handler import build_notification_service
    except Exception as exc:  # pragma: no cover - 依赖缺失时静默
        return {"skipped": True, "error": str(exc)}
    try:
        service = build_notification_service()
        return await service.send_notification(payload, reason)
    except Exception as exc:  # pragma: no cover
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# 编排入口
# ---------------------------------------------------------------------------
async def run_weekly_check(
    *,
    week_start: date | None = None,
    week_end: date | None = None,
    dry_run: bool | None = None,
    notify: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    """每周判定入口。可由调度器调用，也可由 API 手动触发。"""
    cfg = MonitorConfig.from_env()
    if dry_run is not None:
        cfg = MonitorConfig(
            auto_disable_enabled=cfg.auto_disable_enabled,
            dry_run=dry_run,
            keep_view_growth=cfg.keep_view_growth,
            keep_want_growth=cfg.keep_want_growth,
            min_days_with_data=cfg.min_days_with_data,
            protect_days=cfg.protect_days,
            max_mute_per_week=cfg.max_mute_per_week,
        )

    if week_start is None or week_end is None:
        computed_start, computed_end = last_full_week(now.astimezone(SHANGHAI_TZ).date() if now else None)
        week_start = week_start or computed_start
        week_end = week_end or computed_end

    if not cfg.auto_disable_enabled and not cfg.dry_run:
        # 总开关关闭且非影子模式 → 不执行任何动作
        return {
            "skipped": True,
            "reason": "MONITOR_AUTO_DISABLE_ENABLED=false 且 MONITOR_DRY_RUN=false，未执行判定",
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
        }

    decisions = await asyncio.to_thread(
        lambda: evaluate_week(week_start, week_end, config=cfg, now=now)
    )
    await asyncio.to_thread(_persist_decisions_sync, decisions)

    to_mute = [d for d in decisions if d.action in (ACTION_MUTED, ACTION_DRY_RUN)]

    # 熔断上限
    capped = False
    if cfg.max_mute_per_week and len(to_mute) > cfg.max_mute_per_week:
        capped = True
        overflow = to_mute[cfg.max_mute_per_week:]
        to_mute = to_mute[: cfg.max_mute_per_week]
        for decision in overflow:
            decision.action = ACTION_SKIPPED
            decision.reason = (
                f"超出单周停用上限 MONITOR_MAX_MUTE_PER_WEEK={cfg.max_mute_per_week}，本轮跳过"
            )
        await asyncio.to_thread(_persist_decisions_sync, overflow)

    muted_count = 0
    if to_mute and not cfg.dry_run:
        muted_count = await asyncio.to_thread(
            lambda: mute_items_sync(
                [{"seller_user_id": d.seller_user_id, "item_id": d.item_id} for d in to_mute],
                reason=f"周增长不达标（{week_start} ~ {week_end}）",
                week_start=week_start,
            )
        )

    notification_result: dict | None = None
    if notify and to_mute:
        payload = build_notification_payload(
            to_mute, week_start=week_start, week_end=week_end, dry_run=cfg.dry_run
        )
        reason = (
            f"这些商品在 {week_start} ~ {week_end} 一周内浏览/想要均无有效增长，"
            f"已{'标记（试运行，未实际停用）' if cfg.dry_run else '停止监控'}。"
            f"如需恢复请在监控健康度页面操作。"
        )
        notification_result = await _send_notification(payload, reason)

    summary = {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "dry_run": cfg.dry_run,
        "evaluated": len(decisions),
        "kept": sum(1 for d in decisions if d.action == ACTION_KEPT),
        "skipped": sum(1 for d in decisions if d.action == ACTION_SKIPPED),
        "interrupted": sum(1 for d in decisions if d.action == ACTION_INTERRUPTED),
        "would_mute": sum(1 for d in decisions if d.action in (ACTION_MUTED, ACTION_DRY_RUN))
        + (0 if not capped else 0),
        "muted": muted_count,
        "capped": capped,
        "notified": bool(notification_result),
        "notification": notification_result,
        "decided_at": shanghai_now_iso(),
    }
    return summary


def run_weekly_check_sync(**kwargs) -> dict[str, Any]:
    return asyncio.run(run_weekly_check(**kwargs))


# ---------------------------------------------------------------------------
# 查询（供 API / 前端）
# ---------------------------------------------------------------------------
def list_health_decisions_sync(
    *,
    week_start: date | None = None,
    action: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    bootstrap_storage()
    conditions: list[str] = []
    params: list[Any] = []
    if week_start:
        conditions.append("week_start = ?")
        params.append(week_start.isoformat())
    if action:
        conditions.append("action = ?")
        params.append(action)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
        SELECT week_start, week_end, seller_user_id, item_id, title,
               days_with_data, view_start, view_end, view_growth,
               want_start, want_end, want_growth,
               healthy, reason, action, decided_at
        FROM item_monitor_health_weekly
        {where}
        ORDER BY week_start DESC, view_growth ASC, want_growth ASC
        LIMIT ?
    """
    params.append(limit)
    with db_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        for key in ("week_start", "week_end"):
            if hasattr(payload.get(key), "isoformat"):
                payload[key] = payload[key].isoformat()
        decided_at = payload.get("decided_at")
        if hasattr(decided_at, "isoformat"):
            payload["decided_at"] = decided_at.isoformat()
        results.append(payload)
    return results


def latest_week_sync() -> date | None:
    bootstrap_storage()
    with db_connection() as conn:
        row = conn.execute(
            "SELECT MAX(week_start) AS latest FROM item_monitor_health_weekly"
        ).fetchone()
    return _parse_date(row["latest"]) if row and row.get("latest") else None

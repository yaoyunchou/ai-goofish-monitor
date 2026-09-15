"""店铺 datacompass 快照存储。"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any

from src.infrastructure.persistence.db_connection import db_connection
from src.infrastructure.persistence.sql_dialect import json_text, parse_json_field
from src.infrastructure.persistence.storage_bootstrap import bootstrap_storage


def _snapshot_date(parsed: dict) -> str:
    date_range = parsed.get("date_range") or []
    if date_range:
        raw = str(date_range[-1])
        if len(raw) == 8 and raw.isdigit():
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
        return raw
    return date.today().isoformat()


def upsert_snapshot_sync(
    *,
    account_state_file: str,
    shop_name: str | None,
    time_cycle: str,
    parsed: dict,
    raw: dict | None = None,
) -> None:
    bootstrap_storage()
    api_name = parsed.get("api_name") or "unknown"
    snapshot_date = _snapshot_date(parsed)
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO shop_datacompass_snapshots (
                account_state_file, shop_name, time_cycle, snapshot_date,
                api_name, metrics_json, raw_json, captured_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (account_state_file, time_cycle, snapshot_date, api_name)
            DO UPDATE SET
                shop_name = EXCLUDED.shop_name,
                metrics_json = EXCLUDED.metrics_json,
                raw_json = EXCLUDED.raw_json,
                captured_at = EXCLUDED.captured_at
            """,
            (
                account_state_file,
                shop_name,
                time_cycle,
                snapshot_date,
                api_name,
                json_text(parsed),
                json_text(raw) if raw is not None else None,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()


def list_latest_by_cycle_sync(time_cycle: str = "1d", account_state_file: str | None = None) -> list[dict[str, Any]]:
    bootstrap_storage()
    conditions = ["time_cycle = ?"]
    params: list = [time_cycle]
    if account_state_file:
        conditions.append("account_state_file = ?")
        params.append(account_state_file)
    sql = f"""
        SELECT DISTINCT ON (api_name)
            account_state_file, shop_name, time_cycle, snapshot_date, api_name,
            metrics_json, captured_at
        FROM shop_datacompass_snapshots
        WHERE {' AND '.join(conditions)}
        ORDER BY api_name, captured_at DESC
    """
    with db_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["metrics"] = parse_json_field(item.pop("metrics_json"), default={})
        captured_at = item.get("captured_at")
        if captured_at is not None:
            item["captured_at"] = captured_at.isoformat() if hasattr(captured_at, "isoformat") else str(captured_at)
        snapshot_date = item.get("snapshot_date")
        if snapshot_date is not None:
            item["snapshot_date"] = snapshot_date.isoformat() if hasattr(snapshot_date, "isoformat") else str(snapshot_date)
        result.append(item)
    return result


def list_metric_trend_sync(metric: str, days: int = 30, time_cycle: str = "1d") -> list[dict[str, Any]]:
    bootstrap_storage()
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT snapshot_date, api_name, metrics_json, captured_at
            FROM shop_datacompass_snapshots
            WHERE time_cycle = ?
            ORDER BY snapshot_date ASC, captured_at ASC
            """,
            (time_cycle,),
        ).fetchall()
    points = []
    for row in rows:
        parsed = parse_json_field(row["metrics_json"], default={})
        metrics = parsed.get("metrics") or {}
        if metric not in metrics:
            continue
        points.append({
            "date": str(row["snapshot_date"]),
            "api_name": row["api_name"],
            "value": (metrics.get(metric) or {}).get("value"),
            "prev": (metrics.get(metric) or {}).get("prev"),
            "ratio": (metrics.get(metric) or {}).get("ratio"),
        })
    return points[-max(days, 1) :]


async def upsert_snapshot(**kwargs) -> None:
    await asyncio.to_thread(lambda: upsert_snapshot_sync(**kwargs))


async def list_latest_by_cycle(time_cycle: str = "1d", account_state_file: str | None = None):
    return await asyncio.to_thread(list_latest_by_cycle_sync, time_cycle, account_state_file)


async def list_metric_trend(metric: str, days: int = 30, time_cycle: str = "1d"):
    return await asyncio.to_thread(list_metric_trend_sync, metric, days, time_cycle)

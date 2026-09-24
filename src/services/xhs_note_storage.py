"""笔记与上海日指标。同一天覆盖，没解析到的字段保留当天原值。"""
from __future__ import annotations

import os
import time
from datetime import datetime

from src.domain.xhs_note_parse import parse_note_id
from src.domain.xhs_parse import is_note_link, is_short_link
from src.infrastructure.persistence import db_connection as db_connection_module
from src.services.monitor_accounts import LOGIN_MISSING, mark_account_checked, mark_account_error, resolve_xhs_account
from src.time_utils import shanghai_now, shanghai_today
from src.xhs_collector import fetch_public
from src.xhs_note_collector import NOTE_GAP_SECONDS, NoteBrowser, fields_of

DEFAULT_CRON = "0 9 * * *"
NOTE_LINK_MESSAGE = "这是笔记，请到笔记菜单添加"
_COUNT_FIELDS = ("liked_count", "collected_count", "comment_count", "view_count")


def _conn():
    return db_connection_module.db_connection()


def _ensure(conn) -> None:
    db_connection_module.ensure_incremental_schema(conn)


def add_note(url: str, *, account_id: int | None = None) -> dict:
    source = (url or "").strip()
    if not source:
        raise ValueError("请填写笔记链接")
    if is_short_link(source) and not is_note_link(source):
        fetched = fetch_public(source)
        if fetched.final_url:
            source = fetched.final_url
    if not is_note_link(source):
        raise ValueError("请粘贴小红书笔记链接")
    note_id = parse_note_id(source)
    if note_id is None:
        raise ValueError("无法从链接解析笔记 ID")
    with _conn() as conn:
        _ensure(conn)
        existing = conn.execute("SELECT id FROM xhs_notes WHERE id = ?", (note_id,)).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO xhs_notes (id, source_url, account_id, active, updated_at)
                VALUES (?, ?, ?, TRUE, now())
                """,
                (note_id, source, account_id),
            )
        else:
            conn.execute(
                """
                UPDATE xhs_notes
                SET source_url = ?, active = TRUE, last_error = NULL, last_status = NULL,
                    account_id = COALESCE(?, account_id), updated_at = now()
                WHERE id = ?
                """,
                (source, account_id, note_id),
            )
        conn.commit()
    row = get_note(note_id)
    row["created"] = existing is None
    return row


def get_note(note_id: str) -> dict:
    with _conn() as conn:
        _ensure(conn)
        row = conn.execute("SELECT * FROM xhs_notes WHERE id = ?", (note_id,)).fetchone()
    if row is None:
        raise KeyError(note_id)
    return dict(row)


def list_notes() -> list[dict]:
    with _conn() as conn:
        _ensure(conn)
        notes = conn.execute(
            "SELECT * FROM xhs_notes WHERE active = TRUE ORDER BY updated_at DESC"
        ).fetchall()
        items = []
        for note in notes:
            days = conn.execute(
                """
                SELECT snapshot_day, liked_count, collected_count, comment_count, view_count
                FROM xhs_note_daily
                WHERE note_id = ?
                ORDER BY snapshot_day DESC
                LIMIT 2
                """,
                (note["id"],),
            ).fetchall()
            items.append(_with_delta(dict(note), days))
    return items


def deactivate_note(note_id: str) -> None:
    with _conn() as conn:
        _ensure(conn)
        conn.execute(
            "UPDATE xhs_notes SET active = FALSE, updated_at = now() WHERE id = ?",
            (note_id,),
        )
        conn.commit()


def get_schedule() -> dict:
    with _conn() as conn:
        _ensure(conn)
        row = conn.execute(
            "SELECT cron, enabled, account_id FROM xhs_note_schedule WHERE id = 1"
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO xhs_note_schedule (id, cron, enabled) VALUES (1, ?, FALSE)",
                (DEFAULT_CRON,),
            )
            conn.commit()
            return {"cron": DEFAULT_CRON, "enabled": False, "account_id": None}
    return {
        "cron": row["cron"],
        "enabled": bool(row["enabled"]),
        "account_id": row["account_id"],
    }


def save_schedule(cron: str, enabled: bool, account_id: int | None) -> dict:
    expression = (cron or "").strip() or DEFAULT_CRON
    with _conn() as conn:
        _ensure(conn)
        conn.execute(
            """
            INSERT INTO xhs_note_schedule (id, cron, enabled, account_id, updated_at)
            VALUES (1, ?, ?, ?, now())
            ON CONFLICT (id) DO UPDATE SET
                cron = EXCLUDED.cron,
                enabled = EXCLUDED.enabled,
                account_id = EXCLUDED.account_id,
                updated_at = now()
            """,
            (expression, enabled, account_id),
        )
        conn.commit()
    return {"cron": expression, "enabled": enabled, "account_id": account_id}


def collect_notes(
    note_id: str | None = None,
    *,
    state_dir: str | None = None,
    opener=None,
    gap_seconds: float = NOTE_GAP_SECONDS,
    now: datetime | None = None,
) -> dict:
    current = now or shanghai_now()
    schedule = get_schedule()
    with _conn() as conn:
        _ensure(conn)
        if note_id:
            rows = conn.execute(
                "SELECT * FROM xhs_notes WHERE id = ? AND active = TRUE",
                (note_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM xhs_notes WHERE active = TRUE ORDER BY id"
            ).fetchall()
    notes = [dict(row) for row in rows]
    if not notes:
        return {"saved": 0, "failed": 0, "stopped": False, "error": None}
    account_id = notes[0].get("account_id") or schedule.get("account_id")
    directory = state_dir or os.environ.get("ACCOUNT_STATE_DIR", "state")
    account, path = resolve_xhs_account(account_id, directory)
    if path is None:
        _mark_login_required(notes)
        return {
            "saved": 0,
            "failed": len(notes),
            "stopped": True,
            "error": LOGIN_MISSING,
        }
    saved = 0
    failed = 0
    stopped = False
    error = None
    browser = None
    try:
        for index, note in enumerate(notes):
            if index and gap_seconds:
                time.sleep(gap_seconds)
            if opener is not None:
                result = opener(path, note["source_url"])
            else:
                if browser is None:
                    browser = NoteBrowser(path)
                    browser.__enter__()
                result = browser.fetch(note["source_url"])
            parsed = fields_of(result)
            if parsed.login_required:
                stopped = True
                error = "登录已失效"
                mark_account_error(int(account["id"]), error)
                _set_status(note["id"], "login_required", error, parsed)
                failed += 1
                break
            if result.error and parsed.liked_count is None and parsed.collected_count is None:
                _set_status(note["id"], "failed", result.error, parsed)
                failed += 1
                error = error or result.error
                continue
            _save_day(note["id"], parsed, current)
            _set_status(note["id"], "ok", None, parsed)
            saved += 1
    finally:
        if browser is not None:
            browser.__exit__(None, None, None)
    if saved and account is not None and not stopped:
        mark_account_checked(int(account["id"]))
    return {"saved": saved, "failed": failed, "stopped": stopped, "error": error}


def _mark_login_required(notes: list[dict]) -> None:
    for note in notes:
        _set_status(note["id"], "login_required", LOGIN_MISSING, None)


def _set_status(note_id: str, status: str, error: str | None, parsed) -> None:
    with _conn() as conn:
        _ensure(conn)
        title = parsed.title if parsed is not None else None
        author = parsed.author_name if parsed is not None else None
        cover = parsed.cover_url if parsed is not None else None
        conn.execute(
            """
            UPDATE xhs_notes
            SET last_status = ?, last_error = ?,
                title = COALESCE(?, title),
                author_name = COALESCE(?, author_name),
                cover_url = COALESCE(?, cover_url),
                updated_at = now()
            WHERE id = ?
            """,
            (status, error, title, author, cover, note_id),
        )
        conn.commit()


def _save_day(note_id: str, parsed, now: datetime) -> None:
    day = shanghai_today(now)
    with _conn() as conn:
        _ensure(conn)
        conn.execute(
            """
            INSERT INTO xhs_note_daily (
                note_id, snapshot_day, liked_count, collected_count, comment_count, view_count, captured_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (note_id, snapshot_day) DO UPDATE SET
                liked_count = COALESCE(EXCLUDED.liked_count, xhs_note_daily.liked_count),
                collected_count = COALESCE(EXCLUDED.collected_count, xhs_note_daily.collected_count),
                comment_count = COALESCE(EXCLUDED.comment_count, xhs_note_daily.comment_count),
                view_count = COALESCE(EXCLUDED.view_count, xhs_note_daily.view_count),
                captured_at = EXCLUDED.captured_at
            """,
            (
                note_id,
                day.isoformat(),
                parsed.liked_count,
                parsed.collected_count,
                parsed.comment_count,
                parsed.view_count,
                now.isoformat(),
            ),
        )
        conn.commit()


def _with_delta(note: dict, days) -> dict:
    latest = days[0] if days else None
    previous = days[1] if len(days) > 1 else None
    metrics = {}
    deltas = {}
    for field in _COUNT_FIELDS:
        current = latest[field] if latest else None
        before = previous[field] if previous else None
        metrics[field] = current
        if current is None or before is None:
            deltas[field] = None
        else:
            deltas[field] = int(current) - int(before)
    note["metrics"] = metrics
    note["deltas"] = deltas
    note["snapshot_day"] = latest["snapshot_day"] if latest else None
    return note

"""账号索引。Cookie 在文件里，表里只记渠道和相对路径。"""
from __future__ import annotations

import os
import re
from pathlib import Path

from src.infrastructure.persistence import db_connection as db_connection_module

ACCOUNT_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,50}$")
CHANNELS = ("goofish", "xhs")
LOGIN_MISSING = "没有可用的小红书登录"


def ensure_accounts(conn) -> None:
    db_connection_module.ensure_incremental_schema(conn)


def sync_goofish_files(state_dir: str) -> None:
    root = Path(state_dir)
    if not root.is_dir():
        return
    with db_connection_module.db_connection() as conn:
        ensure_accounts(conn)
        for path in sorted(root.glob("*.json")):
            name = path.stem
            if not ACCOUNT_NAME_RE.match(name):
                continue
            state_path = path.name
            conn.execute(
                """
                INSERT INTO monitor_accounts (channel, name, state_path)
                VALUES ('goofish', ?, ?)
                ON CONFLICT (channel, name) DO NOTHING
                """,
                (name, state_path),
            )
        conn.commit()


def list_accounts(channel: str | None = None) -> list[dict]:
    with db_connection_module.db_connection() as conn:
        ensure_accounts(conn)
        if channel:
            rows = conn.execute(
                """
                SELECT id, channel, name, state_path, enabled, last_checked_at, last_error
                FROM monitor_accounts
                WHERE channel = ?
                ORDER BY name
                """,
                (channel,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, channel, name, state_path, enabled, last_checked_at, last_error
                FROM monitor_accounts
                ORDER BY channel, name
                """
            ).fetchall()
    return [_public_row(row) for row in rows]


def get_account(channel: str, name: str) -> dict | None:
    with db_connection_module.db_connection() as conn:
        ensure_accounts(conn)
        row = conn.execute(
            """
            SELECT id, channel, name, state_path, enabled, last_checked_at, last_error
            FROM monitor_accounts
            WHERE channel = ? AND name = ?
            """,
            (channel, name),
        ).fetchone()
    return _public_row(row) if row else None


def upsert_account(channel: str, name: str, state_path: str, *, enabled: bool = True) -> dict:
    with db_connection_module.db_connection() as conn:
        ensure_accounts(conn)
        conn.execute(
            """
            INSERT INTO monitor_accounts (channel, name, state_path, enabled, updated_at)
            VALUES (?, ?, ?, ?, now())
            ON CONFLICT (channel, name) DO UPDATE SET
                state_path = EXCLUDED.state_path,
                enabled = EXCLUDED.enabled,
                updated_at = now()
            """,
            (channel, name, state_path, enabled),
        )
        conn.commit()
    row = get_account(channel, name)
    if row is None:
        raise RuntimeError("账号写入后读不到")
    return row


def delete_account_row(channel: str, name: str) -> None:
    with db_connection_module.db_connection() as conn:
        ensure_accounts(conn)
        conn.execute(
            "DELETE FROM monitor_accounts WHERE channel = ? AND name = ?",
            (channel, name),
        )
        conn.commit()


def mark_account_error(account_id: int, message: str) -> None:
    with db_connection_module.db_connection() as conn:
        ensure_accounts(conn)
        conn.execute(
            """
            UPDATE monitor_accounts
            SET last_error = ?, last_checked_at = now(), updated_at = now()
            WHERE id = ?
            """,
            (message, account_id),
        )
        conn.commit()


def mark_account_checked(account_id: int) -> None:
    with db_connection_module.db_connection() as conn:
        ensure_accounts(conn)
        conn.execute(
            """
            UPDATE monitor_accounts
            SET last_error = NULL, last_checked_at = now(), updated_at = now()
            WHERE id = ?
            """,
            (account_id,),
        )
        conn.commit()


def resolve_xhs_account(account_id: int | None, state_dir: str) -> tuple[dict | None, str | None]:
    """返回 (账号行, 绝对路径)。不可用时路径为空，并带上原因在账号错误里。"""
    with db_connection_module.db_connection() as conn:
        ensure_accounts(conn)
        if account_id is not None:
            row = conn.execute(
                """
                SELECT id, channel, name, state_path, enabled, last_checked_at, last_error
                FROM monitor_accounts
                WHERE id = ? AND channel = 'xhs' AND enabled = TRUE
                """,
                (account_id,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT id, channel, name, state_path, enabled, last_checked_at, last_error
                FROM monitor_accounts
                WHERE channel = 'xhs' AND enabled = TRUE
                ORDER BY id
                LIMIT 1
                """
            ).fetchone()
    if row is None:
        return None, None
    account = _public_row(row)
    path = os.path.join(state_dir, account["state_path"].replace("/", os.sep))
    if not os.path.isfile(path):
        mark_account_error(int(account["id"]), LOGIN_MISSING)
        return account, None
    return account, path


def _public_row(row) -> dict:
    return {
        "id": row["id"],
        "channel": row["channel"],
        "name": row["name"],
        "state_path": row["state_path"],
        "enabled": bool(row["enabled"]),
        "last_checked_at": row["last_checked_at"],
        "last_error": row["last_error"],
    }

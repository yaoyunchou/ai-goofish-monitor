#!/usr/bin/env python3
"""
将线上 PostgreSQL（Supabase）业务表同步到本地 DATABASE_URL。

用法:
  # .env 中配置 REMOTE_DATABASE_URL（线上 Session pooler，勿提交仓库）
  python -m scripts.sync_postgres_remote_to_local
  python -m scripts.sync_postgres_remote_to_local --dry-run
  python -m scripts.sync_postgres_remote_to_local --remote-url "postgresql://..."

默认会清空本地 6 张业务表后按主键顺序全量写入（保留远程 id）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.infrastructure.config.env_manager import env_manager  # noqa: E402
from src.infrastructure.persistence.database_config import get_postgres_dsn  # noqa: E402

TABLE_ORDER = (
    "app_metadata",
    "tasks",
    "result_items",
    "price_snapshots",
    "result_blacklist_rules",
    "collected_items",
)

TRUNCATE_SQL = """
TRUNCATE TABLE
    collected_items,
    result_blacklist_rules,
    price_snapshots,
    result_items,
    tasks,
    app_metadata
RESTART IDENTITY CASCADE;
"""

JSONB_COLS = {
    "keyword_rules_json",
    "raw_json",
    "tags_json",
    "blacklist_keywords_json",
    "sku_json",
}

PRESERVE_ID = {"tasks", "result_items", "price_snapshots", "collected_items"}


def _normalize_dsn(url: str) -> str:
    url = url.strip()
    url = re.sub(r"^postgresql\+asyncpg://", "postgresql://", url, count=1)
    url = re.sub(r"^postgresql\+psycopg://", "postgresql://", url, count=1)
    if not url.startswith("postgresql://"):
        raise RuntimeError("连接串必须以 postgresql:// 或 postgresql+asyncpg:// 开头")
    return url


def _remote_dsn(cli_url: str | None) -> str:
    if cli_url:
        return _normalize_dsn(cli_url)
    raw = env_manager.get_value("REMOTE_DATABASE_URL")
    if not raw:
        raise RuntimeError(
            "请设置 REMOTE_DATABASE_URL（线上 Supabase Session pooler），"
            "或使用 --remote-url 传入"
        )
    return _normalize_dsn(str(raw))


def _mask_dsn(dsn: str) -> str:
    if "@" not in dsn:
        return dsn
    prefix, rest = dsn.split("@", 1)
    if "://" in prefix:
        scheme, _auth = prefix.split("://", 1)
        return f"{scheme}://***@{rest}"
    return f"***@{rest}"


def _adapt_row(table: str, row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if key in JSONB_COLS and value is not None and not isinstance(value, str):
            out[key] = json.dumps(value, ensure_ascii=False)
        else:
            out[key] = value
    return out


def _insert_batch(cur, table: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    rows = [_adapt_row(table, dict(row)) for row in rows]
    columns = list(rows[0].keys())
    col_list = ", ".join(columns)
    parts = []
    for col in columns:
        if col in JSONB_COLS:
            parts.append(f"%({col})s::jsonb")
        else:
            parts.append(f"%({col})s")
    values_sql = ", ".join(parts)
    overriding = " OVERRIDING SYSTEM VALUE" if table in PRESERVE_ID else ""
    sql = f"INSERT INTO {table} ({col_list}){overriding} VALUES ({values_sql})"
    cur.executemany(sql, rows)
    return len(rows)


def _reset_sequences(cur, table: str) -> None:
    if table not in PRESERVE_ID:
        return
    cur.execute(
        f"""
        SELECT setval(
            pg_get_serial_sequence('{table}', 'id'),
            COALESCE((SELECT MAX(id) FROM {table}), 1),
            true
        )
        """
    )


def _fetch_table(remote_conn, table: str) -> list[dict[str, Any]]:
    with remote_conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {table}")
        cols = [d.name for d in cur.description]
        rows: list[dict[str, Any]] = []
        for raw in cur.fetchall():
            row = {cols[i]: raw[i] for i in range(len(cols))}
            rows.append(_adapt_row(table, row))
        return rows


def sync(*, remote_url: str | None, dry_run: bool) -> int:
    import psycopg
    from psycopg.rows import dict_row

    remote_dsn = _remote_dsn(remote_url)
    local_dsn = get_postgres_dsn()
    print(f"源（线上）: {_mask_dsn(remote_dsn)}")
    print(f"目标（本地）: {_mask_dsn(local_dsn)}")
    if dry_run:
        print("模式: dry-run\n")

    with psycopg.connect(remote_dsn, row_factory=dict_row) as remote_conn:
        snapshots: dict[str, list[dict[str, Any]]] = {}
        for table in TABLE_ORDER:
            rows = _fetch_table(remote_conn, table)
            snapshots[table] = rows
            print(f"  读取 {table}: {len(rows)} 行")

    if dry_run:
        print("\n完成（未写入本地）。")
        return 0

    with psycopg.connect(local_dsn, row_factory=dict_row) as local_conn:
        with local_conn.cursor() as cur:
            cur.execute(TRUNCATE_SQL)
            for table in TABLE_ORDER:
                n = _insert_batch(cur, table, snapshots[table])
                _reset_sequences(cur, table)
                print(f"  写入 {table}: {n} 行")
        local_conn.commit()

    print("\n同步完成。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="线上 Postgres → 本地 Postgres 全量同步")
    parser.add_argument("--remote-url", type=str, default="", help="覆盖 REMOTE_DATABASE_URL")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    remote = args.remote_url.strip() or None
    return sync(remote_url=remote, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

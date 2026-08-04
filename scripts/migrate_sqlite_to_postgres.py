#!/usr/bin/env python3
"""
将本地 SQLite（data/app.sqlite3）历史数据一次性迁入 PostgreSQL（.env 中 DATABASE_URL）。

用法:
  python3 -m scripts.migrate_sqlite_to_postgres --source data/app.sqlite3
  python3 -m scripts.migrate_sqlite_to_postgres --source /path/to/app.sqlite3 --dry-run
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.infrastructure.persistence.database_config import get_postgres_dsn  # noqa: E402
from src.infrastructure.persistence.storage_names import DEFAULT_DATABASE_PATH  # noqa: E402

TABLE_ORDER = (
    "app_metadata",
    "tasks",
    "result_items",
    "price_snapshots",
    "result_blacklist_rules",
    "collected_items",
)

TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "app_metadata": ("key", "value"),
    "tasks": (
        "id", "task_name", "enabled", "keyword", "description", "analyze_images",
        "max_pages", "personal_only", "min_price", "max_price", "cron",
        "ai_prompt_base_file", "ai_prompt_criteria_file", "account_state_file",
        "account_strategy", "free_shipping", "new_publish_option", "region",
        "decision_mode", "keyword_rules_json", "is_running",
    ),
    "result_items": (
        "id", "result_filename", "keyword", "task_name", "crawl_time", "publish_time",
        "price", "price_display", "item_id", "title", "link", "link_unique_key",
        "seller_nickname", "is_recommended", "analysis_source", "keyword_hit_count",
        "status", "raw_json",
    ),
    "price_snapshots": (
        "id", "keyword_slug", "keyword", "task_name", "snapshot_time", "snapshot_day",
        "run_id", "item_id", "title", "price", "price_display", "tags_json", "region",
        "seller", "publish_time", "link",
    ),
    "result_blacklist_rules": (
        "result_filename", "blacklist_keywords_json", "updated_at",
    ),
    "collected_items": (
        "id", "result_item_id", "collected_at", "sku_fetch_status",
        "sku_fetched_at", "sku_json", "sku_error",
    ),
}

PRESERVE_ID = {
    "tasks", "result_items", "price_snapshots", "collected_items",
}

JSONB_COLS = {
    "keyword_rules_json", "raw_json", "tags_json", "blacklist_keywords_json", "sku_json",
}

BOOL_COLS = {
    "enabled", "analyze_images", "personal_only", "free_shipping", "is_running", "is_recommended",
}


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.OperationalError:
        return set()
    return {str(r[1]) for r in rows}


def _normalize_value(col: str, value: Any) -> Any:
    if value is None:
        return None
    if col in BOOL_COLS:
        return bool(int(value))
    if col in JSONB_COLS:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        text = str(value).strip()
        if not text:
            return "[]"
        json.loads(text)
        return text
    return value


def _read_sqlite_table(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    wanted = TABLE_COLUMNS[table]
    existing = _sqlite_columns(conn, table)
    if not existing:
        return []
    select_cols = [c for c in wanted if c in existing]
    if not select_cols:
        return []
    sql = f"SELECT {', '.join(select_cols)} FROM {table}"
    cur = conn.execute(sql)
    out: list[dict[str, Any]] = []
    for raw in cur.fetchall():
        row = {select_cols[i]: raw[i] for i in range(len(select_cols))}
        record: dict[str, Any] = {}
        for col in wanted:
            if col in row:
                record[col] = _normalize_value(col, row[col])
            elif col == "status" and table == "result_items":
                record[col] = "active"
            else:
                record[col] = None
        out.append(record)
    return out


def _insert_rows(pg_conn, table: str, rows: list[dict[str, Any]], *, dry_run: bool) -> int:
    if not rows:
        return 0
    if dry_run:
        return len(rows)

    columns = TABLE_COLUMNS[table]
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

    if table == "app_metadata":
        sql += " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
    elif table == "tasks":
        sql += " ON CONFLICT (id) DO NOTHING"
    elif table == "result_items":
        sql += " ON CONFLICT (result_filename, link_unique_key) DO NOTHING"
    elif table == "price_snapshots":
        sql += " ON CONFLICT (keyword_slug, run_id, item_id) DO NOTHING"
    elif table == "collected_items":
        sql += " ON CONFLICT (result_item_id) DO NOTHING"

    with pg_conn.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)


def _pg_count(pg_conn, table: str) -> int:
    with pg_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return int(cur.fetchone()[0])


def _sqlite_count(conn: sqlite3.Connection, table: str) -> int:
    if not _sqlite_columns(conn, table):
        return 0
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.OperationalError:
        return 0


def _reset_sequence(pg_conn, table: str) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', 'id'),
                COALESCE((SELECT MAX(id) FROM {table}), 1),
                true
            )
            """
        )


def migrate(source: Path, *, dry_run: bool, tables: list[str] | None) -> int:
    if not source.is_file():
        print(f"错误: SQLite 文件不存在: {source}", file=sys.stderr)
        return 1

    import psycopg

    selected = [t for t in TABLE_ORDER if not tables or t in tables]
    print(f"源 SQLite: {source.resolve()}")
    print(f"目标: DATABASE_URL（Postgres）")
    print("表:", ", ".join(selected))
    if dry_run:
        print("模式: dry-run\n")

    sqlite_conn = sqlite3.connect(str(source))
    try:
        with psycopg.connect(get_postgres_dsn()) as pg_conn:
            for table in selected:
                rows = _read_sqlite_table(sqlite_conn, table)
                before = _pg_count(pg_conn, table) if not dry_run else 0
                n = _insert_rows(pg_conn, table, rows, dry_run=dry_run)
                if not dry_run:
                    pg_conn.commit()
                    after = _pg_count(pg_conn, table)
                    if table in PRESERVE_ID:
                        _reset_sequence(pg_conn, table)
                        pg_conn.commit()
                else:
                    after = before + n
                print(
                    f"  {table}: sqlite={_sqlite_count(sqlite_conn, table)} "
                    f"写入={n}" + (f" postgres={after}" if not dry_run else "")
                )
    finally:
        sqlite_conn.close()

    print("\n完成。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite → PostgreSQL 数据迁移")
    parser.add_argument("--source", type=Path, default=Path(DEFAULT_DATABASE_PATH))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--tables", type=str, default="", help="逗号分隔，默认全部")
    args = parser.parse_args()
    tables = [t.strip() for t in args.tables.split(",") if t.strip()] or None
    return migrate(args.source, dry_run=args.dry_run, tables=tables)


if __name__ == "__main__":
    raise SystemExit(main())

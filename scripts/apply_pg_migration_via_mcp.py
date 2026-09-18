#!/usr/bin/env python3
"""按表导出 SQL 到 data/pg_migration/tables/，便于分批导入。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_pg_migration_sql import _sql_literal
from scripts.migrate_postgres_to_postgres import TABLES

OUT_DIR = _REPO_ROOT / "data" / "pg_migration" / "tables"


def _insert_lines(table: str, row: dict, columns: list[str]) -> str:
    col_sql = ", ".join(columns)
    vals = ", ".join(_sql_literal(row[c]) for c in columns)
    if table == "seller_subscription_schedule":
        return (
            f"INSERT INTO {table} ({col_sql}) VALUES ({vals}) ON CONFLICT (id) DO UPDATE SET "
            + ", ".join(f"{c}=EXCLUDED.{c}" for c in columns if c != "id")
            + ";"
        )
    if table == "app_metadata":
        return (
            f"INSERT INTO {table} ({col_sql}) VALUES ({vals}) "
            f"ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value;"
        )
    if table == "seller_subscriptions":
        return (
            f"INSERT INTO {table} ({col_sql}) VALUES ({vals}) ON CONFLICT (seller_user_id) DO UPDATE SET "
            + ", ".join(f"{c}=EXCLUDED.{c}" for c in columns if c != "id")
            + ";"
        )
    return f"INSERT INTO {table} ({col_sql}) VALUES ({vals});"


def main() -> int:
    from src.infrastructure.persistence.db_connection import db_connection

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    with db_connection() as conn:
        for table in TABLES:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            if not rows:
                manifest[table] = 0
                continue
            columns = list(rows[0].keys())
            chunks: list[str] = []
            if table != "seller_subscription_schedule":
                chunks.append(f"DELETE FROM {table};")
            batch: list[str] = []
            for row in rows:
                batch.append(_insert_lines(table, dict(row), columns))
                if table == "result_items" and len(batch) >= 5:
                    chunks.extend(batch)
                    batch = []
            chunks.extend(batch)
            path = OUT_DIR / f"{table}.sql"
            path.write_text("\n".join(chunks) + "\n", encoding="utf-8")
            manifest[table] = len(rows)
            print(f"{table}: {len(rows)} rows -> {path.name} ({path.stat().st_size} bytes)")
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

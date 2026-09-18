#!/usr/bin/env python3
"""从当前源库导出 INSERT SQL，供 Supabase MCP 或 psql 导入目标库。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.migrate_postgres_to_postgres import TABLES

OUTPUT = _REPO_ROOT / "data" / "pg_migration.sql"


def _sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        return "'" + json.dumps(value, ensure_ascii=False).replace("'", "''") + "'::jsonb"
    text = str(value).replace("'", "''")
    return f"'{text}'"


def main() -> int:
    from psycopg.rows import dict_row

    from src.infrastructure.persistence.db_connection import db_connection

    lines = ["BEGIN;", "SET session_replication_role = replica;"]
    with db_connection() as conn:
        for table in TABLES:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            if not rows:
                continue
            lines.append(f"-- {table} ({len(rows)} rows)")
            if table != "seller_subscription_schedule":
                lines.append(f"DELETE FROM {table};")
            columns = list(rows[0].keys())
            col_sql = ", ".join(columns)
            for row in rows:
                vals = ", ".join(_sql_literal(row[c]) for c in columns)
                if table == "seller_subscription_schedule":
                    lines.append(
                        f"INSERT INTO {table} ({col_sql}) VALUES ({vals}) "
                        f"ON CONFLICT (id) DO UPDATE SET "
                        + ", ".join(f"{c}=EXCLUDED.{c}" for c in columns if c != "id")
                        + ";"
                    )
                elif table == "app_metadata":
                    lines.append(
                        f"INSERT INTO {table} ({col_sql}) VALUES ({vals}) "
                        f"ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value;"
                    )
                elif table == "seller_subscriptions":
                    lines.append(
                        f"INSERT INTO {table} ({col_sql}) VALUES ({vals}) "
                        f"ON CONFLICT (seller_user_id) DO UPDATE SET "
                        + ", ".join(f"{c}=EXCLUDED.{c}" for c in columns if c != "id")
                        + ";"
                    )
                else:
                    lines.append(f"INSERT INTO {table} ({col_sql}) VALUES ({vals});")

    lines.append("SET session_replication_role = origin;")
    for table, seq in {
        "tasks": "tasks_id_seq",
        "result_items": "result_items_id_seq",
        "price_snapshots": "price_snapshots_id_seq",
        "seller_profiles": "seller_profiles_id_seq",
        "seller_item_metrics": "seller_item_metrics_id_seq",
        "seller_subscriptions": "seller_subscriptions_id_seq",
    }.items():
        lines.append(
            f"SELECT setval('{seq}', COALESCE((SELECT MAX(id) FROM {table}), 1), "
            f"(SELECT COUNT(*) > 0 FROM {table}));"
        )
    lines.append("COMMIT;")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已导出 {OUTPUT} ({len(lines)} 行 SQL)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

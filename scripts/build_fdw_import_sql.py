#!/usr/bin/env python3
"""生成在新加坡库执行的 postgres_fdw 拉取 SQL（从东京源库导入）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

SOURCE_HOST = "db.wkhatdhgohkpsqkytotz.supabase.co"
TABLES = [
    "result_items",
    "price_snapshots",
    "seller_profiles",
]


def _load_password() -> str:
    text = Path(_REPO_ROOT / ".env").read_text(encoding="utf-8")
    m = re.search(r"DATABASE_URL=postgresql\+asyncpg://postgres\.[^:]+:([^@]+)@", text)
    if not m:
        raise RuntimeError("无法从 .env 解析 DATABASE_URL 密码")
    return m.group(1)


def _pg_type(data_type: str, udt_name: str) -> str:
    if data_type == "ARRAY":
        return f"{udt_name.replace('_', '')}[]"
    if data_type == "USER-DEFINED" and udt_name == "jsonb":
        return "jsonb"
    mapping = {
        "bigint": "bigint",
        "integer": "integer",
        "double precision": "double precision",
        "numeric": "numeric",
        "boolean": "boolean",
        "text": "text",
        "timestamp with time zone": "timestamptz",
        "date": "date",
        "jsonb": "jsonb",
    }
    return mapping.get(data_type, "text")


def main() -> int:
    from src.infrastructure.persistence.db_connection import db_connection

    password = _load_password()
    lines = [
        "CREATE EXTENSION IF NOT EXISTS postgres_fdw;",
        "DROP SERVER IF EXISTS tokyo_source CASCADE;",
        f"""
CREATE SERVER tokyo_source FOREIGN DATA WRAPPER postgres_fdw OPTIONS (
    host '{SOURCE_HOST}', port '5432', dbname 'postgres'
);
""".strip(),
        f"""
CREATE USER MAPPING FOR postgres SERVER tokyo_source OPTIONS (
    user 'postgres', password '{password.replace("'", "''")}'
);
""".strip(),
    ]

    with db_connection() as conn:
        for table in TABLES:
            cols = conn.execute(
                """
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = ?
                ORDER BY ordinal_position
                """,
                (table,),
            ).fetchall()
            col_defs = ", ".join(
                f"{c['column_name']} {_pg_type(c['data_type'], c['udt_name'])}" for c in cols
            )
            col_names = ", ".join(c["column_name"] for c in cols)
            ft = f"ft_{table}"
            lines.append(f"DROP FOREIGN TABLE IF EXISTS {ft};")
            lines.append(
                f"CREATE FOREIGN TABLE {ft} ({col_defs}) "
                f"SERVER tokyo_source OPTIONS (schema_name 'public', table_name '{table}');"
            )
            lines.append(f"DELETE FROM {table};")
            lines.append(f"INSERT INTO {table} ({col_names}) SELECT {col_names} FROM {ft};")
            if table in {"result_items", "price_snapshots", "seller_profiles"}:
                seq = f"{table}_id_seq"
                lines.append(
                    f"SELECT setval('{seq}', COALESCE((SELECT MAX(id) FROM {table}), 1), "
                    f"(SELECT COUNT(*) > 0 FROM {table}));"
                )

    out = _REPO_ROOT / "data" / "pg_migration" / "fdw_import.sql"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    print(out)
    print("statements", len(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

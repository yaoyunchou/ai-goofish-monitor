#!/usr/bin/env python3
"""将 Postgres 数据从源库复制到目标库（Supabase 区域迁移用）。

用法:
  python -m scripts.migrate_postgres_to_postgres \\
    --target-url "postgresql://postgres.<ref>:<password>@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"

源库读取当前 .env 的 DATABASE_URL；目标库通过 --target-url 或环境变量 TARGET_DATABASE_URL 指定。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# 按外键依赖顺序复制
TABLES = [
    "app_metadata",
    "tasks",
    "result_items",
    "price_snapshots",
    "result_blacklist_rules",
    "collected_items",
    "seller_profiles",
    "seller_item_metrics",
    "shop_datacompass_snapshots",
    "seller_subscriptions",
    "seller_subscription_schedule",
]

SEQUENCE_TABLES = {
    "tasks": "tasks_id_seq",
    "result_items": "result_items_id_seq",
    "price_snapshots": "price_snapshots_id_seq",
    "collected_items": "collected_items_id_seq",
    "seller_profiles": "seller_profiles_id_seq",
    "seller_item_metrics": "seller_item_metrics_id_seq",
    "shop_datacompass_snapshots": "shop_datacompass_snapshots_id_seq",
    "seller_subscriptions": "seller_subscriptions_id_seq",
}


def _normalize_dsn(url: str) -> str:
    url = url.strip()
    url = re.sub(r"^postgresql\+asyncpg://", "postgresql://", url, count=1)
    url = re.sub(r"^postgresql\+psycopg://", "postgresql://", url, count=1)
    return url


def _copy_table(src_conn, dst_conn, table: str) -> int:
    import psycopg
    from psycopg import sql
    from psycopg.types.json import Json

    rows = src_conn.execute(f"SELECT * FROM {table}").fetchall()
    if not rows:
        return 0

    columns = list(rows[0].keys())
    col_identifiers = sql.SQL(", ").join(sql.Identifier(c) for c in columns)
    placeholders = sql.SQL(", ").join(sql.Placeholder() * len(columns))
    insert_sql = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
        sql.Identifier(table),
        col_identifiers,
        placeholders,
    )

    with dst_conn.cursor() as cur:
        cur.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(table)))
        for row in rows:
            values = []
            for col in columns:
                val = row[col]
                if isinstance(val, (dict, list)):
                    val = Json(val)
                values.append(val)
            cur.execute(insert_sql, values)
    dst_conn.commit()
    return len(rows)


def _fix_sequences(dst_conn) -> None:
    for table, seq in SEQUENCE_TABLES.items():
        dst_conn.execute(
            f"""
            SELECT setval(
                '{seq}',
                COALESCE((SELECT MAX(id) FROM {table}), 1),
                (SELECT COUNT(*) > 0 FROM {table})
            )
            """
        )
    dst_conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Postgres 库间数据迁移")
    parser.add_argument("--target-url", default=None, help="目标 DATABASE_URL")
    parser.add_argument("--dry-run", action="store_true", help="仅统计源库行数")
    args = parser.parse_args()

    from src.infrastructure.persistence.database_config import get_postgres_dsn

    source_dsn = _normalize_dsn(get_postgres_dsn())
    target_dsn = _normalize_dsn(args.target_url or __import__("os").environ.get("TARGET_DATABASE_URL", ""))
    if not args.dry_run and not target_dsn:
        print("请提供 --target-url 或环境变量 TARGET_DATABASE_URL", file=sys.stderr)
        return 1

    import psycopg
    from psycopg.rows import dict_row

    print("连接源库…")
    with psycopg.connect(source_dsn, row_factory=dict_row, connect_timeout=15) as src:
        counts = {}
        for table in TABLES:
            row = src.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            counts[table] = int(row["n"])
        print("源库行数:", json.dumps(counts, ensure_ascii=False))

        if args.dry_run:
            return 0

        print("连接目标库…")
        with psycopg.connect(target_dsn, row_factory=dict_row, connect_timeout=15) as dst:
            total = 0
            for table in TABLES:
                if counts.get(table, 0) == 0:
                    continue
                copied = _copy_table(src, dst, table)
                print(f"  {table}: {copied} 行")
                total += copied
            _fix_sequences(dst)
            print(f"迁移完成，共 {total} 行。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

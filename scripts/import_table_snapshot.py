#!/usr/bin/env python3
"""从 data/db_sync_snapshot/<table>.json 覆盖单表（不清空其它表）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.sync_postgres_remote_to_local import _insert_batch, _reset_sequences  # noqa: E402
from src.infrastructure.persistence.database_config import get_postgres_dsn  # noqa: E402

SNAPSHOT_DIR = _REPO / "data" / "db_sync_snapshot"


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python import_table_snapshot.py <table>", file=sys.stderr)
        return 1
    table = sys.argv[1].strip()
    fp = SNAPSHOT_DIR / f"{table}.json"
    if not fp.is_file():
        print(f"缺少 {fp}", file=sys.stderr)
        return 1
    rows = json.loads(fp.read_text(encoding="utf-8"))

    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(get_postgres_dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {table}")
            n = _insert_batch(cur, table, rows)
            _reset_sequences(cur, table)
            print(f"写入 {table}: {n}")
        conn.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

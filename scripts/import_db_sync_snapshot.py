#!/usr/bin/env python3
"""从 data/db_sync_snapshot/*.json 全量覆盖写入本地 Postgres。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.sync_postgres_remote_to_local import (  # noqa: E402
    TABLE_ORDER,
    TRUNCATE_SQL,
    _insert_batch,
    _reset_sequences,
)
from src.infrastructure.persistence.database_config import get_postgres_dsn  # noqa: E402

SNAPSHOT_DIR = _REPO / "data" / "db_sync_snapshot"


def main() -> int:
    import psycopg
    from psycopg.rows import dict_row

    snapshots: dict[str, list] = {}
    for table in TABLE_ORDER:
        fp = SNAPSHOT_DIR / f"{table}.json"
        if not fp.is_file():
            print(f"缺少 {fp}", file=sys.stderr)
            return 1
        snapshots[table] = json.loads(fp.read_text(encoding="utf-8"))
        print(f"加载 {table}: {len(snapshots[table])}")

    with psycopg.connect(get_postgres_dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(TRUNCATE_SQL)
            for table in TABLE_ORDER:
                n = _insert_batch(cur, table, snapshots[table])
                _reset_sequences(cur, table)
                print(f"写入 {table}: {n}")
        conn.commit()
    print("完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

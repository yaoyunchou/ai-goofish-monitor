#!/usr/bin/env python3
"""从 REMOTE_DATABASE_URL 拉取业务表到 data/db_sync_snapshot/。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.sync_postgres_remote_to_local import TABLE_ORDER, _fetch_table  # noqa: E402
from scripts.sync_postgres_remote_to_local import _remote_dsn  # noqa: E402

OUT = _REPO / "data" / "db_sync_snapshot"


def main() -> int:
    import psycopg
    from psycopg.rows import dict_row

    remote_dsn = _remote_dsn(None)
    OUT.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(remote_dsn, row_factory=dict_row) as conn:
        for table in TABLE_ORDER:
            rows = _fetch_table(conn, table)
            (OUT / f"{table}.json").write_text(
                json.dumps(rows, ensure_ascii=False), encoding="utf-8"
            )
            print(f"{table}: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

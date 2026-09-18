#!/usr/bin/env python3
"""Execute one SQL file against DATABASE_URL (sync psycopg)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg


def db_url() -> str:
    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        env = Path(__file__).resolve().parents[1] / ".env"
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                raw = line.split("=", 1)[1].strip()
                break
    return raw.replace("postgresql+asyncpg://", "postgresql://")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _pg_exec_sql_file.py <sql-file>", file=sys.stderr)
        return 1
    path = Path(sys.argv[1])
    query = path.read_text(encoding="utf-8")
    with psycopg.connect(db_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
        conn.commit()
    print(f"ok len={len(query)} path={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

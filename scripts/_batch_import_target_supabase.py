#!/usr/bin/env python3
"""Batch-execute pg_migration SQL files against target Supabase Postgres."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts._run_supabase_import import collect_files  # noqa: E402


def _dsn() -> str:
    out = subprocess.check_output(
        [sys.executable, str(REPO / "scripts" / "_build_target_dsn.py")],
        text=True,
    )
    return out.strip()


def main() -> int:
    import psycopg

    files = collect_files()
    dsn = _dsn()
    errors: list[str] = []
    ok: list[str] = []
    conn = psycopg.connect(dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for i, meta in enumerate(files):
                name = meta["name"]
                sql = Path(meta["path"]).read_text(encoding="utf-8")
                try:
                    cur.execute(sql)
                    ok.append(name)
                    print(f"OK [{i}] {name}")
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{name}: {exc}")
                    print(f"ERR [{i}] {name}: {exc}", file=sys.stderr)
    finally:
        conn.close()
    print("---")
    print(f"success: {len(ok)}/{len(files)}")
    if errors:
        print("errors:")
        for e in errors:
            print(f"  - {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

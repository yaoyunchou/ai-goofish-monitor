#!/usr/bin/env python3
"""Read SQL migration files for Supabase MCP import."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def collect_files() -> list[dict]:
    files: list[dict] = []
    files.append(
        {
            "name": "seller_profiles.sql",
            "path": str(REPO / "data/pg_migration/tables/seller_profiles.sql"),
        }
    )
    for table in ("result_items", "price_snapshots"):
        chunk_dir = REPO / f"data/pg_migration/tables/chunks/{table}"
        for p in sorted(chunk_dir.glob("*.sql")):
            files.append({"name": f"{table}/{p.name}", "path": str(p)})
    return files


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _run_supabase_import.py list|read <index>")
        return 1
    cmd = sys.argv[1]
    files = collect_files()
    if cmd == "list":
        print(json.dumps(files, indent=2))
        return 0
    if cmd == "read":
        idx = int(sys.argv[2])
        path = Path(files[idx]["path"])
        sys.stdout.write(path.read_text(encoding="utf-8"))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

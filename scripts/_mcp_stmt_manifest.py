#!/usr/bin/env python3
"""Build manifest of all SQL statements for MCP import (split by semicolon)."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
OUT = DATA / "mcp_stmt_manifest.json"

STEPS: list[Path] = [REPO / "data/pg_migration/tables/seller_profiles.sql"]
STEPS += sorted((REPO / "data/pg_migration/tables/chunks/result_items").glob("*.sql"))
STEPS += sorted((REPO / "data/pg_migration/tables/chunks/price_snapshots").glob("*.sql"))


def split_sql(text: str) -> list[str]:
    parts = [p.strip() for p in text.split(";") if p.strip()]
    return [p + ";" for p in parts]


def main() -> int:
    manifest: list[dict] = []
    for step_idx, path in enumerate(STEPS):
        if not path.exists():
            manifest.append({"step": step_idx, "label": str(path), "error": "missing"})
            continue
        sql = path.read_text(encoding="utf-8")
        for stmt_idx, stmt in enumerate(split_sql(sql)):
            manifest.append(
                {
                    "id": len(manifest),
                    "step": step_idx,
                    "stmt": stmt_idx,
                    "label": f"{path.name}#{stmt_idx}",
                    "query_len": len(stmt),
                    "query": stmt,
                }
            )
    OUT.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"statements": len(manifest), "out": str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

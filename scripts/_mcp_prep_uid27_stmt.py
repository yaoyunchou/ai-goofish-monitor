#!/usr/bin/env python3
"""Prepare one uid27 stmt for agent CallDynamicTool execute_sql.

Usage: python scripts/_mcp_prep_uid27_stmt.py 05
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROJECT_ID = "vcojlixcuqinanjlflgd"
CHUNK_DIR = REPO / "data" / "mcp_chunks_uid27"
OUT = REPO / "data" / ".invoke_args.json"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _mcp_prep_uid27_stmt.py <stmt_num e.g. 05>", file=sys.stderr)
        return 1
    num = sys.argv[1]
    path = CHUNK_DIR / f"stmt_{num}.sql"
    if not path.exists():
        print(json.dumps({"error": f"missing {path}"}), file=sys.stderr)
        return 1
    query = path.read_text(encoding="utf-8")
    payload = {"project_id": PROJECT_ID, "query": query}
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"stmt": num, "query_len": len(query), "path": str(path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Load one SQL file into data/.invoke_args.json for MCP execute_sql."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INVOKE = REPO / "data" / ".invoke_args.json"
PROJECT_ID = "vcojlixcuqinanjlflgd"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _mcp_load_stmt_invoke.py <sql-file>", file=sys.stderr)
        return 1
    path = Path(sys.argv[1])
    query = path.read_text(encoding="utf-8")
    payload = {"project_id": PROJECT_ID, "query": query}
    INVOKE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"path": str(path), "query_len": len(query)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

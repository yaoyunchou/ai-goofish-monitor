#!/usr/bin/env python3
"""Emit MCP execute_sql payload for one statement file (json to stdout)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ID = "vcojlixcuqinanjlflgd"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _mcp_stmt_payload.py <sql-file>", file=sys.stderr)
        return 1
    path = Path(sys.argv[1])
    query = path.read_text(encoding="utf-8")
    payload = {"project_id": PROJECT_ID, "query": query, "query_len": len(query), "path": str(path)}
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

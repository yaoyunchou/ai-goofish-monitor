#!/usr/bin/env python3
"""Load batch step SQL into JSON for agent MCP call."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROJECT_ID = "vcojlixcuqinanjlflgd"


def main() -> int:
    step = sys.argv[1]
    sql_path = REPO / "data" / "_mcp_batch" / f"{step}.sql"
    q = sql_path.read_text(encoding="utf-8")
    out = REPO / "data" / "_mcp_call_args.json"
    out.write_text(json.dumps({"project_id": PROJECT_ID, "query": q}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"step": step, "query_len": len(q), "args_file": str(out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

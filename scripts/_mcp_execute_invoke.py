#!/usr/bin/env python3
"""Load data/.invoke_args.json via json.load; emit MCP execute_sql args for agent CallDynamicTool.

Usage:
  python scripts/_mcp_execute_invoke.py          # print project_id + query_len
  python scripts/_mcp_execute_invoke.py --emit # print full JSON args to stdout (utf-8)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

INVOKE = Path(__file__).resolve().parents[1] / "data" / ".invoke_args.json"


def main() -> int:
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    payload = {"project_id": args["project_id"], "query": args["query"]}
    if "--emit" in sys.argv:
        sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        return 0
    print(json.dumps({"project_id": payload["project_id"], "query_len": len(payload["query"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

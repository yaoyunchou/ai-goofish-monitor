#!/usr/bin/env python3
"""Apply one MCP import step: read data/.invoke_args.json and print execution metadata.

Agent workflow:
  python scripts/_mcp_sequential_import.py
  python scripts/_mcp_apply_invoke.py --check
  # CallDynamicTool execute_sql with json.load(.invoke_args.json)
  python scripts/_mcp_sequential_import.py --mark <label> ok <next_index>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

INVOKE = Path(__file__).resolve().parents[1] / "data" / ".invoke_args.json"


def main() -> int:
    if not INVOKE.exists():
        print(json.dumps({"error": f"missing {INVOKE}"}), file=sys.stderr)
        return 1
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    meta = {
        "project_id": args["project_id"],
        "query_len": len(args["query"]),
        "query_sha256": __import__("hashlib").sha256(args["query"].encode("utf-8")).hexdigest(),
        "invoke_path": str(INVOKE),
    }
    if "--check" in sys.argv:
        print(json.dumps(meta, ensure_ascii=False))
        return 0
    # default: write sidecar for agent verification
    sidecar = INVOKE.with_suffix(".meta.json")
    sidecar.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

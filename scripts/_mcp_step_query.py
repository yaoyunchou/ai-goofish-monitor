#!/usr/bin/env python3
"""Load query from data/.invoke_args.json via json.load; write plain SQL for agent MCP call."""
from __future__ import annotations

import json
import sys
from pathlib import Path

INVOKE = Path(__file__).resolve().parents[1] / "data" / ".invoke_args.json"
OUT = Path(__file__).resolve().parents[1] / "data" / ".query_only.sql"


def main() -> int:
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    OUT.write_text(args["query"], encoding="utf-8")
    print(json.dumps({"project_id": args["project_id"], "query_len": len(args["query"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

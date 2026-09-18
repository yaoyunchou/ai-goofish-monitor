#!/usr/bin/env python3
"""Load data/.invoke_args.json via json.load and print MCP execute_sql payload to stdout."""
from __future__ import annotations

import json
import sys
from pathlib import Path

INVOKE = Path(__file__).resolve().parents[1] / "data" / ".invoke_args.json"


def main() -> int:
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    print(json.dumps({"project_id": args["project_id"], "query": args["query"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

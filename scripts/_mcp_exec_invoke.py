#!/usr/bin/env python3
"""Load data/.invoke_args.json and emit MCP execute_sql arguments as JSON to stdout."""
from __future__ import annotations

import json
import sys
from pathlib import Path

INVOKE = Path(__file__).resolve().parents[1] / "data" / ".invoke_args.json"


def main() -> int:
    if not INVOKE.exists():
        print(json.dumps({"error": f"missing {INVOKE}"}), file=sys.stderr)
        return 1
    payload = json.loads(INVOKE.read_text(encoding="utf-8"))
    sys.stdout.buffer.write(
        json.dumps(
            {"project_id": payload["project_id"], "query": payload["query"]},
            ensure_ascii=False,
        ).encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

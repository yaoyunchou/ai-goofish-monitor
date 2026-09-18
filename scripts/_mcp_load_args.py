#!/usr/bin/env python3
"""Load data/.invoke_args.json and print MCP execute_sql arguments as JSON."""
from __future__ import annotations

import json
import sys
from pathlib import Path

INVOKE = Path(__file__).resolve().parents[1] / "data" / ".invoke_args.json"


def main() -> int:
    payload = json.loads(INVOKE.read_text(encoding="utf-8"))
    sys.stdout.write(
        json.dumps(
            {"project_id": payload["project_id"], "query": payload["query"]},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

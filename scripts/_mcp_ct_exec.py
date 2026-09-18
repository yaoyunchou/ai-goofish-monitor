#!/usr/bin/env python3
"""Load data/.invoke_args.json via json.load; print MCP execute_sql args as JSON to stdout."""
from __future__ import annotations

import json
import sys
from pathlib import Path

INVOKE = Path(__file__).resolve().parents[1] / "data" / ".invoke_args.json"


def main() -> int:
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    payload = {"project_id": args["project_id"], "query": args["query"]}
    if "--check" in sys.argv:
        print(
            json.dumps(
                {
                    "project_id": payload["project_id"],
                    "query_len": len(payload["query"]),
                },
                ensure_ascii=False,
            )
        )
        return 0
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

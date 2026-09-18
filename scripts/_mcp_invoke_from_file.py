#!/usr/bin/env python3
"""Load MCP execute_sql args from data/.invoke_args.json (stdout: metadata only)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

INVOKE = Path(__file__).resolve().parents[1] / "data" / ".invoke_args.json"


def main() -> int:
    if not INVOKE.exists():
        print(json.dumps({"error": f"missing {INVOKE}"}), file=sys.stderr)
        return 1
    payload = json.loads(INVOKE.read_text(encoding="utf-8"))
    q = payload["query"]
    print(
        json.dumps(
            {
                "project_id": payload["project_id"],
                "query_len": len(q),
                "query_sha256": hashlib.sha256(q.encode("utf-8")).hexdigest(),
                "query_tail": q[-40:],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

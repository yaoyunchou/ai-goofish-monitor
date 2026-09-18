#!/usr/bin/env python3
"""Validate current .invoke_args.json step; agent must CallDynamicTool execute_sql next."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

INVOKE = Path(__file__).resolve().parents[1] / "data" / ".invoke_args.json"
QUERY_OUT = Path(__file__).resolve().parents[1] / "data" / ".current_query.sql"


def main() -> int:
    if not INVOKE.exists():
        print(json.dumps({"error": "missing invoke_args"}), file=sys.stderr)
        return 1
    payload = json.loads(INVOKE.read_text(encoding="utf-8"))
    query = payload["query"]
    QUERY_OUT.write_text(query, encoding="utf-8")
    meta = {
        "project_id": payload["project_id"],
        "query_len": len(query),
        "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
        "query_path": str(QUERY_OUT),
        "invoke_path": str(INVOKE),
    }
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

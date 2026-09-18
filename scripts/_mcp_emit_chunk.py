#!/usr/bin/env python3
"""Emit one chunk payload JSON for agent CallDynamicTool execute_sql.

Usage: python scripts/_mcp_emit_chunk.py 3
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    i = int(sys.argv[1])
    p = REPO / "data" / f"_chunk_{i}.json"
    if not p.exists():
        print(json.dumps({"error": f"missing {p}"}), file=sys.stderr)
        return 1
    payload = json.loads(p.read_text(encoding="utf-8"))
    print(json.dumps({"i": i, "query_len": len(payload["query"]), "project_id": payload["project_id"]}))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

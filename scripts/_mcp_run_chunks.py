#!/usr/bin/env python3
"""Print chunk SQL files for agent CallDynamicTool loop.

Usage:
  python scripts/_mcp_run_chunks.py list 23
  python scripts/_mcp_run_chunks.py show 23 3
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROJECT_ID = "vcojlixcuqinanjlflgd"


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: _mcp_run_chunks.py list|show <row_id> [chunk_i]", file=sys.stderr)
        return 1
    cmd = sys.argv[1]
    row_id = int(sys.argv[2])
    chunk_dir = REPO / "data" / f"mcp_chunks_uid{row_id}"
    manifest = json.loads((chunk_dir / "manifest.json").read_text(encoding="utf-8"))
    if cmd == "list":
        print(json.dumps({"project_id": PROJECT_ID, "chunks": manifest}, indent=2))
        return 0
    if cmd == "show":
        i = int(sys.argv[3])
        sql = (chunk_dir / f"stmt_{i:02d}.sql").read_text(encoding="utf-8")
        payload = {"project_id": PROJECT_ID, "query": sql, "query_len": len(sql), "chunk": i}
        sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        return 0
    print(f"unknown cmd: {cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

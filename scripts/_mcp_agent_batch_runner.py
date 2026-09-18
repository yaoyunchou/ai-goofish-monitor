#!/usr/bin/env python3
"""Agent batch runner: prepare -> emit query file -> (agent MCP) -> done.

Usage:
  python scripts/_mcp_agent_batch_runner.py next [batch_size]
  python scripts/_mcp_agent_batch_runner.py done
  python scripts/_mcp_agent_batch_runner.py status
  python scripts/_mcp_agent_batch_runner.py load   # full invoke args JSON to stdout
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
INVOKE = DATA / ".invoke_args.json"
QUERY_OUT = DATA / "_query_only.txt"
BATCH = REPO / "scripts" / "_mcp_batch_inserts.py"
QUEUE = DATA / "mcp_unit_queue.json"
SKIP = REPO / "scripts" / "_mcp_import_skip_delete.py"


def next_batch(batch_size: int = 3) -> dict:
    out = json.loads(
        subprocess.check_output([sys.executable, str(BATCH), "prepare", str(batch_size)], cwd=REPO).decode()
    )
    if out.get("action") == "done":
        return out
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    QUERY_OUT.write_text(args["query"], encoding="utf-8")
    return {
        **out,
        "query_file": str(QUERY_OUT),
        "invoke_path": str(INVOKE),
    }


def mark_done() -> dict:
    return json.loads(subprocess.check_output([sys.executable, str(BATCH), "done"], cwd=REPO).decode())


def status() -> dict:
    state = json.loads(QUEUE.read_text(encoding="utf-8"))
    return {
        "next_uid": state["next_uid"],
        "total_units": len(state["units"]),
        "done_count": len(state["done_uids"]),
        "remaining": len(state["units"]) - state["next_uid"],
    }


def load_invoke() -> dict:
    return json.loads(INVOKE.read_text(encoding="utf-8"))


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "next"
    if cmd == "next":
        size = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        print(json.dumps(next_batch(size), ensure_ascii=False))
        return 0
    if cmd == "done":
        print(json.dumps(mark_done(), ensure_ascii=False))
        return 0
    if cmd == "status":
        print(json.dumps(status(), ensure_ascii=False))
        return 0
    if cmd == "load":
        sys.stdout.buffer.write(
            json.dumps(load_invoke(), ensure_ascii=False).encode("utf-8")
        )
        return 0
    print("usage: next [batch_size]|done|status|load", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

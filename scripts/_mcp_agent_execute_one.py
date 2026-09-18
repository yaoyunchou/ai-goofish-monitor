#!/usr/bin/env python3
"""Prepare next INSERT unit (skip DELETE) for agent CallDynamicTool execute_sql.

Usage:
  python scripts/_mcp_agent_execute_one.py prepare   # -> data/.invoke_args.json + metadata JSON
  python scripts/_mcp_agent_execute_one.py done      # mark current unit ok
  python scripts/_mcp_agent_execute_one.py status    # queue next_uid / done count
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKIP = REPO / "scripts" / "_mcp_import_skip_delete.py"
BATCH_DONE = REPO / "scripts" / "_mcp_batch_inserts.py"
QUEUE = REPO / "data" / "mcp_unit_queue.json"


def prepare() -> dict:
    out = json.loads(subprocess.check_output([sys.executable, str(SKIP), "next"], cwd=REPO).decode())
    if out.get("action") == "done":
        return out
    return {
        "action": "execute",
        "uid": out["uid"],
        "label": out["label"],
        "project_id": out["project_id"],
        "query_len": out["query_len"],
        "query_sha256": out["query_sha256"],
        "invoke_path": str(REPO / "data" / ".invoke_args.json"),
    }


def done() -> dict:
    batch_state = REPO / "data" / ".mcp_batch_state.json"
    if batch_state.exists():
        return json.loads(subprocess.check_output([sys.executable, str(BATCH_DONE), "done"], cwd=REPO).decode())
    return json.loads(subprocess.check_output([sys.executable, str(SKIP), "done"], cwd=REPO).decode())


def status() -> dict:
    state = json.loads(QUEUE.read_text(encoding="utf-8"))
    return {
        "next_uid": state["next_uid"],
        "total_units": len(state["units"]),
        "done_count": len(state["done_uids"]),
        "remaining": len(state["units"]) - state["next_uid"],
    }


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    if cmd == "prepare":
        print(json.dumps(prepare(), ensure_ascii=False))
        return 0
    if cmd == "done":
        print(json.dumps(done(), ensure_ascii=False))
        return 0
    if cmd == "status":
        print(json.dumps(status(), ensure_ascii=False))
        return 0
    print("usage: prepare|done|status", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

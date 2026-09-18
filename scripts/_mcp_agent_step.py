#!/usr/bin/env python3
"""One import step: prepare next batch/unit and print invoke summary for MCP agent."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
INVOKE = DATA / ".invoke_args.json"
QUEUE = DATA / "mcp_unit_queue.json"
BATCH_STATE = DATA / ".mcp_batch_state.json"
APPLY = REPO / "scripts" / "_mcp_apply_invoke.py"
BATCH = REPO / "scripts" / "_mcp_batch_inserts.py"
RUN = REPO / "scripts" / "_mcp_run_unit.py"


def load_queue() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def next_unit_size() -> int:
    state = load_queue()
    uid = state["next_uid"]
    if uid >= len(state["units"]):
        return 0
    return state["units"][uid]["query_len"]


def prepare() -> dict:
    state = load_queue()
    if state["next_uid"] >= len(state["units"]):
        return {"action": "complete", "next_uid": state["next_uid"]}
    size = next_unit_size()
    if size > 25000:
        out = json.loads(subprocess.check_output([sys.executable, str(BATCH), "prepare", "1"], cwd=REPO).decode())
    else:
        out = json.loads(subprocess.check_output([sys.executable, str(BATCH), "prepare", "2"], cwd=REPO).decode())
    if out.get("action") == "done" and not out.get("skipped_delete_uids"):
        return {"action": "complete", "next_uid": out["next_uid"]}
    check = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
    invoke = json.loads(INVOKE.read_text(encoding="utf-8"))
    return {
        "action": out.get("action", "execute"),
        "batch": out,
        "check": check,
        "invoke_path": str(INVOKE),
        "project_id": invoke["project_id"],
        "query_len": len(invoke["query"]),
    }


def mark_done() -> dict:
    if BATCH_STATE.exists():
        out = json.loads(subprocess.check_output([sys.executable, str(BATCH), "done"], cwd=REPO).decode())
    else:
        out = json.loads(subprocess.check_output([sys.executable, str(RUN), "done"], cwd=REPO).decode())
    state = load_queue()
    return {"marked": out, "next_uid": state["next_uid"], "remaining": len(state["units"]) - state["next_uid"]}


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    if cmd == "prepare":
        print(json.dumps(prepare(), ensure_ascii=False))
        return 0
    if cmd == "done":
        print(json.dumps(mark_done(), ensure_ascii=False))
        return 0
    print("usage: prepare|done", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

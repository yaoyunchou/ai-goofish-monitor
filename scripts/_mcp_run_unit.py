#!/usr/bin/env python3
"""Prepare current queue unit for MCP; verify via json.load(.invoke_args.json).

Usage:
  python scripts/_mcp_queue_all.py          # rebuild queue from progress
  python scripts/_mcp_run_unit.py prepare   # next unit -> .invoke_args.json
  python scripts/_mcp_run_unit.py verify
  python scripts/_mcp_run_unit.py done      # mark unit ok, advance queue
  python scripts/_mcp_run_unit.py status
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
INVOKE = DATA / ".invoke_args.json"
QUEUE = DATA / "mcp_unit_queue.json"
APPLY = REPO / "scripts" / "_mcp_apply_invoke.py"
SEQ = REPO / "scripts" / "_mcp_sequential_import.py"


def load_queue() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def save_queue(state: dict) -> None:
    QUEUE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def prepare() -> dict:
    state = load_queue()
    uid = state["next_uid"]
    if uid >= len(state["units"]):
        return {"done": True, "next_uid": uid}
    unit = state["units"][uid]
    query = Path(unit["query_file"]).read_text(encoding="utf-8")
    payload = {"project_id": unit["project_id"], "query": query}
    INVOKE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    check = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
    if check["query_len"] != len(query):
        raise SystemExit(f"query_len mismatch {check['query_len']} vs {len(query)}")
    return {"uid": uid, "unit": unit, "query_len": check["query_len"], "query_sha256": check["query_sha256"]}


def done() -> dict:
    state = load_queue()
    uid = state["next_uid"]
    unit = state["units"][uid]
    state["done_uids"].append(uid)
    state["next_uid"] = uid + 1
    if unit.get("step_index") is not None and unit.get("is_last_stmt_of_step"):
        subprocess.check_call(
            [sys.executable, str(SEQ), "--mark", unit["label"], "ok", str(unit["next_index_after_step"])],
            cwd=REPO,
        )
    save_queue(state)
    return {"marked_uid": uid, "next_uid": state["next_uid"], "label": unit["label"]}


def status() -> dict:
    state = load_queue()
    progress = json.loads((DATA / "mcp_import_progress.json").read_text(encoding="utf-8"))
    return {"queue": state, "progress": progress}


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    if cmd == "prepare":
        print(json.dumps(prepare(), ensure_ascii=False))
        return 0
    if cmd == "verify":
        args = json.loads(INVOKE.read_text(encoding="utf-8"))
        print(len(args["query"]))
        return 0
    if cmd == "done":
        print(json.dumps(done(), ensure_ascii=False))
        return 0
    if cmd == "status":
        print(json.dumps(status(), ensure_ascii=False))
        return 0
    print("usage: prepare|verify|done|status", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

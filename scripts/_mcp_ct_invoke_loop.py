#!/usr/bin/env python3
"""Prepare next MCP batch; agent must CallDynamicTool execute_sql with json.load(.invoke_args.json).

Usage:
  python scripts/_mcp_ct_invoke_loop.py next
  # CallDynamicTool execute_sql with json.load(data/.invoke_args.json) full query
  python scripts/_mcp_ct_invoke_loop.py done
  python scripts/_mcp_ct_invoke_loop.py status
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
BATCH = REPO / "scripts" / "_mcp_batch_inserts.py"
RUN_UNIT = REPO / "scripts" / "_mcp_run_unit.py"
APPLY = REPO / "scripts" / "_mcp_apply_invoke.py"
LARGE = 25000
SMALL = 15000


def queue() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def batch_size_for(uid: int, st: dict) -> int:
    unit = st["units"][uid]
    if unit.get("query_len", 0) > LARGE:
        return 1
    n = 2
    for j in range(1, n):
        if uid + j >= len(st["units"]):
            break
        nxt = st["units"][uid + j]
        if nxt["label"] in ("__count__", "__setval__"):
            break
        if nxt.get("query_len", 0) > LARGE:
            break
        if unit.get("query_len", 0) < SMALL and nxt.get("query_len", 0) < SMALL:
            continue
        return 1
    return n


def next_action() -> dict:
    st = queue()
    uid = st["next_uid"]
    if uid >= len(st["units"]):
        return {"action": "done", "next_uid": uid}
    unit = st["units"][uid]
    if unit["label"] in ("__count__", "__setval__"):
        query = Path(unit["query_file"]).read_text(encoding="utf-8").strip()
        payload = {"project_id": unit["project_id"], "query": query}
        INVOKE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        check = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
        return {
            "action": "execute",
            "mode": "special",
            "uid": uid,
            "label": unit["label"],
            **check,
            "invoke_path": str(INVOKE),
        }
    size = batch_size_for(uid, st)
    prep = json.loads(
        subprocess.check_output([sys.executable, str(BATCH), "prepare", str(size)], cwd=REPO).decode()
    )
    if prep.get("action") == "done":
        return prep
    check = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
    return {"action": "execute", "mode": "batch", **prep, **check, "invoke_path": str(INVOKE)}


def mark_done() -> dict:
    st = queue()
    uid = st["next_uid"]
    if uid < len(st["units"]) and st["units"][uid]["label"] in ("__count__", "__setval__"):
        return json.loads(subprocess.check_output([sys.executable, str(RUN_UNIT), "done"], cwd=REPO).decode())
    return json.loads(subprocess.check_output([sys.executable, str(BATCH), "done"], cwd=REPO).decode())


def status() -> dict:
    st = queue()
    return {
        "next_uid": st["next_uid"],
        "done_count": len(st["done_uids"]),
        "total_units": len(st["units"]),
        "remaining": len(st["units"]) - st["next_uid"],
    }


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "next"
    if cmd == "next":
        print(json.dumps(next_action(), ensure_ascii=False))
        return 0
    if cmd == "done":
        print(json.dumps(mark_done(), ensure_ascii=False))
        return 0
    if cmd == "status":
        print(json.dumps(status(), ensure_ascii=False))
        return 0
    print("usage: next|done|status", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

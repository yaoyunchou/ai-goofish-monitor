#!/usr/bin/env python3
"""Run all remaining result_items batches: prepare -> emit args -> agent MCP -> done.

Prints one line per batch:
  BATCH {"merged_uids":[...], "query_len": N, "args_file": "data/.invoke_args.json"}

Agent must CallDynamicTool execute_sql with json.load(args_file) for each BATCH line,
then run: python scripts/_mcp_run_all_batches.py done

Or run full automation status:
  python scripts/_mcp_run_all_batches.py status
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
STATE = DATA / ".mcp_run_all_state.json"
BATCH = REPO / "scripts" / "_mcp_batch_inserts.py"
RUN_UNIT = REPO / "scripts" / "_mcp_run_unit.py"
LARGE = 30000


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"phase": "insert", "pending_done": False}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def queue_state() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def next_batch() -> dict:
    st = queue_state()
    uid = st["next_uid"]
    if uid >= len(st["units"]):
        return {"action": "done"}
    unit = st["units"][uid]
    if unit["label"] in ("__count__", "__setval__"):
        return {"action": "special", "uid": uid, "label": unit["label"]}

    size = 1 if unit.get("query_len", 0) > LARGE else 3
    prep = json.loads(
        subprocess.check_output([sys.executable, str(BATCH), "prepare", str(size)], cwd=REPO).decode()
    )
    if prep.get("action") == "done":
        return {"action": "done"}
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    save_state({"phase": "insert", "pending_done": True, "prep": prep})
    return {
        "action": "execute",
        "merged_uids": prep.get("merged_uids"),
        "skipped_delete_uids": prep.get("skipped_delete_uids"),
        "query_len": len(args["query"]),
        "args_file": str(INVOKE),
        "project_id": args["project_id"],
    }


def mark_batch_done() -> dict:
    state = load_state()
    if not state.get("pending_done"):
        return {"error": "no pending batch"}
    out = json.loads(subprocess.check_output([sys.executable, str(BATCH), "done"], cwd=REPO).decode())
    save_state({"phase": "insert", "pending_done": False})
    return out


def next_special() -> dict:
    st = queue_state()
    uid = st["next_uid"]
    if uid >= len(st["units"]):
        return {"action": "done"}
    unit = st["units"][uid]
    if unit["label"] not in ("__count__", "__setval__"):
        return {"action": "need_insert"}
    query = Path(unit["query_file"]).read_text(encoding="utf-8").strip()
    payload = {"project_id": unit["project_id"], "query": query}
    INVOKE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    save_state({"phase": "special", "pending_done": True, "uid": uid})
    return {
        "action": "execute",
        "uid": uid,
        "label": unit["label"],
        "query_len": len(query),
        "args_file": str(INVOKE),
        "project_id": unit["project_id"],
    }


def mark_special_done() -> dict:
    out = json.loads(subprocess.check_output([sys.executable, str(RUN_UNIT), "done"], cwd=REPO).decode())
    save_state({"phase": "insert", "pending_done": False})
    return out


def status() -> dict:
    st = queue_state()
    return {
        "next_uid": st["next_uid"],
        "done_count": len(st["done_uids"]),
        "total_units": len(st["units"]),
        "runner_state": load_state(),
    }


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "next"
    if cmd == "next":
        rs = load_state()
        if rs.get("pending_done"):
            print(json.dumps({"action": "pending", "message": "run done first"}, ensure_ascii=False))
            return 1
        st = queue_state()
        uid = st["next_uid"]
        if uid < len(st["units"]) and st["units"][uid]["label"] in ("__count__", "__setval__"):
            print(json.dumps(next_special(), ensure_ascii=False))
            return 0
        print(json.dumps(next_batch(), ensure_ascii=False))
        return 0
    if cmd == "done":
        rs = load_state()
        if rs.get("phase") == "special":
            print(json.dumps(mark_special_done(), ensure_ascii=False))
            return 0
        print(json.dumps(mark_batch_done(), ensure_ascii=False))
        return 0
    if cmd == "status":
        print(json.dumps(status(), ensure_ascii=False))
        return 0
    print("usage: next|done|status", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

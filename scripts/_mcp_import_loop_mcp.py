#!/usr/bin/env python3
"""Loop: prepare batch -> emit invoke args path -> wait for MCP ok marker -> done.

Agent workflow (repeat until status shows next_uid >= 63 done):
  python scripts/_mcp_import_loop_mcp.py next
  # CallDynamicTool execute_sql with json.load(data/.invoke_args.json) — full query
  python scripts/_mcp_import_loop_mcp.py mark-ok
  python scripts/_mcp_import_loop_mcp.py status

When next returns action=special, execute uid 63/64 similarly then mark-ok.
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
OK_MARKER = DATA / ".mcp_batch_ok"
BATCH = REPO / "scripts" / "_mcp_batch_inserts.py"
RUN_UNIT = REPO / "scripts" / "_mcp_run_unit.py"
LARGE = 30000


def queue() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def next_action() -> dict:
    if OK_MARKER.exists():
        OK_MARKER.unlink()
    st = queue()
    uid = st["next_uid"]
    if uid >= len(st["units"]):
        return {"action": "done", "next_uid": uid}
    unit = st["units"][uid]
    if unit["label"] in ("__count__", "__setval__"):
        query = Path(unit["query_file"]).read_text(encoding="utf-8").strip()
        payload = {"project_id": unit["project_id"], "query": query}
        INVOKE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return {
            "action": "execute",
            "mode": "special",
            "uid": uid,
            "label": unit["label"],
            "project_id": unit["project_id"],
            "query_len": len(query),
            "invoke_path": str(INVOKE),
        }
    size = 1 if unit.get("query_len", 0) > LARGE else 3
    prep = json.loads(
        subprocess.check_output([sys.executable, str(BATCH), "prepare", str(size)], cwd=REPO).decode()
    )
    if prep.get("action") == "done":
        return prep
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    return {
        "action": "execute",
        "mode": "batch",
        **prep,
        "query_len": len(args["query"]),
        "invoke_path": str(INVOKE),
    }


def mark_ok() -> dict:
    st = queue()
    uid = st["next_uid"]
    if uid < len(st["units"]) and st["units"][uid]["label"] in ("__count__", "__setval__"):
        out = json.loads(subprocess.check_output([sys.executable, str(RUN_UNIT), "done"], cwd=REPO).decode())
        OK_MARKER.write_text("ok", encoding="utf-8")
        return out
    out = json.loads(subprocess.check_output([sys.executable, str(BATCH), "done"], cwd=REPO).decode())
    OK_MARKER.write_text("ok", encoding="utf-8")
    return out


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
    if cmd == "mark-ok":
        print(json.dumps(mark_ok(), ensure_ascii=False))
        return 0
    if cmd == "status":
        print(json.dumps(status(), ensure_ascii=False))
        return 0
    print("usage: next|mark-ok|status", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Print import status and next batch metadata for agent MCP execute_sql loop."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QUEUE = REPO / "data" / "mcp_unit_queue.json"
INVOKE = REPO / "data" / ".invoke_args.json"
BATCH = REPO / "scripts" / "_mcp_batch_inserts.py"
LARGE = 30000


def queue() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def status() -> dict:
    st = queue()
    return {
        "next_uid": st["next_uid"],
        "total_units": len(st["units"]),
        "done_count": len(st["done_uids"]),
        "remaining": len(st["units"]) - st["next_uid"],
    }


def prepare_next() -> dict:
    st = queue()
    uid = st["next_uid"]
    if uid >= len(st["units"]):
        return {"action": "done"}
    unit = st["units"][uid]
    if unit["label"] in ("__count__", "__setval__"):
        return {"action": "special", "uid": uid, "label": unit["label"]}
    size = 1 if unit.get("query_len", 0) > LARGE else 1
    prep = json.loads(
        subprocess.check_output([sys.executable, str(BATCH), "prepare", str(size)], cwd=REPO).decode()
    )
    if prep.get("action") == "done":
        return prep
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    return {
        "action": "execute",
        "merged_uids": prep.get("merged_uids"),
        "query_len": len(args["query"]),
        "query_sha256": prep.get("query_sha256"),
        "project_id": args["project_id"],
        "invoke_path": str(INVOKE),
    }


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        print(json.dumps(status(), ensure_ascii=False))
        return 0
    if cmd == "prepare":
        print(json.dumps(prepare_next(), ensure_ascii=False))
        return 0
    print("usage: status|prepare", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prepare next queue unit; skip DELETE stmts (except uid 0 already done).

DELETE units are auto-marked done without MCP. INSERT units emit payload for agent MCP.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INVOKE = REPO / "data" / ".invoke_args.json"
QUEUE = REPO / "data" / "mcp_unit_queue.json"
RUN = REPO / "scripts" / "_mcp_run_unit.py"
APPLY = REPO / "scripts" / "_mcp_apply_invoke.py"
DELETE_SQL = "DELETE FROM result_items;"


def load_queue() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def prepare_or_skip() -> dict:
    skipped: list[int] = []
    while True:
        state = load_queue()
        uid = state["next_uid"]
        if uid >= len(state["units"]):
            out = {"action": "done", "next_uid": uid}
            if skipped:
                out["skipped_delete_uids"] = skipped
            return out
        unit = state["units"][uid]
        query = Path(unit["query_file"]).read_text(encoding="utf-8").strip()
        if query == DELETE_SQL and uid > 0:
            subprocess.check_call([sys.executable, str(RUN), "prepare"], cwd=REPO)
            done = json.loads(subprocess.check_output([sys.executable, str(RUN), "done"], cwd=REPO).decode())
            skipped.append(done["marked_uid"])
            continue
        prep = json.loads(subprocess.check_output([sys.executable, str(RUN), "prepare"], cwd=REPO).decode())
        check = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
        args = json.loads(INVOKE.read_text(encoding="utf-8"))
        qlen = len(args["query"])
        if check["query_len"] != qlen:
            raise SystemExit(f"query_len mismatch check={check['query_len']} actual={qlen}")
        out = {
            "action": "execute",
            "uid": prep["uid"],
            "label": prep["unit"]["label"],
            "project_id": args["project_id"],
            "query": args["query"],
            "query_len": qlen,
            "query_sha256": check["query_sha256"],
        }
        if skipped:
            out["skipped_delete_uids"] = skipped
        return out


def mark_done() -> dict:
    return json.loads(subprocess.check_output([sys.executable, str(RUN), "done"], cwd=REPO).decode())


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "next"
    if cmd == "next":
        print(json.dumps(prepare_or_skip(), ensure_ascii=False))
        return 0
    if cmd == "done":
        print(json.dumps(mark_done(), ensure_ascii=False))
        return 0
    print("usage: next|done", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

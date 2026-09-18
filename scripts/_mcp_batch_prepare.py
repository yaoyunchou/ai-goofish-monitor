#!/usr/bin/env python3
"""Process N queue units: prepare + emit query via json.load(.invoke_args.json).

Prints one JSON object per line for agent to CallDynamicTool execute_sql, then run:
  python scripts/_mcp_run_unit.py done

Usage:
  python scripts/_mcp_batch_prepare.py 5   # prepare up to 5 units (one at a time, agent MCP between)
  
Actually runs ONE unit per invocation (queue is sequential):
  python scripts/_mcp_batch_prepare.py      # prepare current unit, print payload
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INVOKE = REPO / "data" / ".invoke_args.json"
RUN = REPO / "scripts" / "_mcp_run_unit.py"
APPLY = REPO / "scripts" / "_mcp_apply_invoke.py"


def prepare_one() -> dict:
    prep = json.loads(subprocess.check_output([sys.executable, str(RUN), "prepare"], cwd=REPO).decode())
    if prep.get("done"):
        return {"action": "done", "next_uid": prep["next_uid"]}
    check = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    qlen = len(args["query"])
    if check["query_len"] != qlen:
        raise SystemExit(f"query_len mismatch check={check['query_len']} actual={qlen}")
    return {
        "action": "execute",
        "uid": prep["uid"],
        "label": prep["unit"]["label"],
        "stmt_index": prep["unit"]["stmt_index"],
        "project_id": args["project_id"],
        "query": args["query"],
        "query_len": qlen,
        "query_sha256": check["query_sha256"],
    }


def mark_done() -> dict:
    return json.loads(subprocess.check_output([sys.executable, str(RUN), "done"], cwd=REPO).decode())


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    if cmd == "prepare":
        print(json.dumps(prepare_one(), ensure_ascii=False))
        return 0
    if cmd == "done":
        print(json.dumps(mark_done(), ensure_ascii=False))
        return 0
    print("usage: prepare|done", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

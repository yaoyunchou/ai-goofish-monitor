#!/usr/bin/env python3
"""Run one import cycle: prepare -> load query via json.load -> write sidecar for MCP -> done on --mark.

Agent workflow per unit:
  python scripts/_mcp_cycle.py prepare
  # CallDynamicTool execute_sql with json.load(data/.invoke_args.json) query
  python scripts/_mcp_cycle.py done

Or batch status:
  python scripts/_mcp_cycle.py status
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


def prepare() -> dict:
    prep = json.loads(subprocess.check_output([sys.executable, str(RUN), "prepare"], cwd=REPO).decode())
    if prep.get("done"):
        return prep
    check = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    qlen = len(args["query"])
    if check["query_len"] != qlen:
        raise SystemExit(f"query_len mismatch check={check['query_len']} actual={qlen}")
    return {
        "action": "execute",
        "uid": prep["uid"],
        "label": prep["unit"]["label"],
        "project_id": args["project_id"],
        "query_len": qlen,
        "query_sha256": check["query_sha256"],
        "invoke_path": str(INVOKE),
    }


def done() -> dict:
    return json.loads(subprocess.check_output([sys.executable, str(RUN), "done"], cwd=REPO).decode())


def status() -> dict:
    return json.loads(subprocess.check_output([sys.executable, str(RUN), "status"], cwd=REPO).decode())


def load_query() -> dict:
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    return {"project_id": args["project_id"], "query": args["query"], "query_len": len(args["query"])}


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
    if cmd == "load":
        print(json.dumps(load_query(), ensure_ascii=False))
        return 0
    print("usage: prepare|done|status|load", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

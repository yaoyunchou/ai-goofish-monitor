#!/usr/bin/env python3
"""Agent helper: prepare one queue unit, emit query via json.load(.invoke_args.json).

Usage:
  python scripts/_mcp_agent_unit_loop.py next   # prepare + write .current_query.sql
  python scripts/_mcp_agent_unit_loop.py done   # mark unit ok
  python scripts/_mcp_agent_unit_loop.py status # queue status
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
INVOKE = DATA / ".invoke_args.json"
OUT = DATA / ".current_query.sql"
RUN = REPO / "scripts" / "_mcp_run_unit.py"
APPLY = REPO / "scripts" / "_mcp_apply_invoke.py"


def next_unit() -> dict:
    prep = json.loads(subprocess.check_output([sys.executable, str(RUN), "prepare"], cwd=REPO).decode())
    if prep.get("done"):
        return prep
    check = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    qlen = len(args["query"])
    if check["query_len"] != qlen:
        raise SystemExit(f"query_len mismatch check={check['query_len']} actual={qlen}")
    OUT.write_text(args["query"], encoding="utf-8")
    return {
        "action": "execute",
        "uid": prep["uid"],
        "label": prep["unit"]["label"],
        "stmt_index": prep["unit"]["stmt_index"],
        "stmt_total": prep["unit"]["stmt_total"],
        "project_id": args["project_id"],
        "query_len": qlen,
        "query_sha256": check["query_sha256"],
        "query_file": str(OUT),
    }


def mark_done() -> dict:
    return json.loads(subprocess.check_output([sys.executable, str(RUN), "done"], cwd=REPO).decode())


def status() -> dict:
    return json.loads(subprocess.check_output([sys.executable, str(RUN), "status"], cwd=REPO).decode())


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "next"
    if cmd == "next":
        print(json.dumps(next_unit(), ensure_ascii=False))
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

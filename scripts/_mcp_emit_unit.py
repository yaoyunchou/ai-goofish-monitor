#!/usr/bin/env python3
"""Emit one queue unit payload via json.load(.invoke_args.json) for agent MCP execute_sql.

  python scripts/_mcp_emit_unit.py next   # prepare + print {project_id, query, uid, ...}
  python scripts/_mcp_emit_unit.py done   # mark current unit ok
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


def next_unit() -> dict:
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
        "stmt_index": prep["unit"]["stmt_index"],
        "stmt_total": prep["unit"]["stmt_total"],
        "project_id": args["project_id"],
        "query": args["query"],
        "query_len": qlen,
        "query_sha256": check["query_sha256"],
    }


def mark_done() -> dict:
    return json.loads(subprocess.check_output([sys.executable, str(RUN), "done"], cwd=REPO).decode())


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "next"
    if cmd == "next":
        print(json.dumps(next_unit(), ensure_ascii=False))
        return 0
    if cmd == "done":
        print(json.dumps(mark_done(), ensure_ascii=False))
        return 0
    print("usage: next|done", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

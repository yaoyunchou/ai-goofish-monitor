#!/usr/bin/env python3
"""Drive remaining result_items MCP import units.

Usage:
  python scripts/_mcp_remaining_driver.py status
  python scripts/_mcp_remaining_driver.py prepare   # -> writes data/.invoke_args.json
  python scripts/_mcp_remaining_driver.py done
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
QUEUE = DATA / "mcp_unit_queue.json"
BATCH_STATE = DATA / ".mcp_batch_state.json"
AGENT = REPO / "scripts" / "_mcp_agent_step.py"
APPLY = REPO / "scripts" / "_mcp_apply_invoke.py"


def load_queue() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def status() -> dict:
    q = load_queue()
    return {
        "next_uid": q["next_uid"],
        "total": len(q["units"]),
        "remaining": len(q["units"]) - q["next_uid"],
        "batch_pending": BATCH_STATE.exists(),
    }


def prepare() -> dict:
    out = json.loads(subprocess.check_output([sys.executable, str(AGENT), "prepare"], cwd=REPO).decode())
    check = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
    return {"prepare": out, "check": check}


def done() -> dict:
    out = json.loads(subprocess.check_output([sys.executable, str(AGENT), "done"], cwd=REPO).decode())
    return {"done": out, "status": status()}


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        print(json.dumps(status(), ensure_ascii=False))
    elif cmd == "prepare":
        print(json.dumps(prepare(), ensure_ascii=False))
    elif cmd == "done":
        print(json.dumps(done(), ensure_ascii=False))
    else:
        print("usage: status|prepare|done", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

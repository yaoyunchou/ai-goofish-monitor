#!/usr/bin/env python3
"""Step through _mcp_exec_plan.json for agent CallDynamicTool loop.

Usage:
  python scripts/_mcp_exec_plan_step.py next [N]   # emit N payloads JSON array
  python scripts/_mcp_exec_plan_step.py advance N  # mark N items done
  python scripts/_mcp_exec_plan_step.py status
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "data" / "_mcp_exec_plan.json"
PROGRESS = REPO / "data" / "_mcp_exec_progress.json"
PROJECT_ID = "vcojlixcuqinanjlflgd"


def load_progress() -> dict:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    return {"index": 0, "done": 0}


def save_progress(state: dict) -> None:
    PROGRESS.write_text(json.dumps(state, indent=2), encoding="utf-8")


def payload_for(item: dict) -> dict | None:
    if item["action"] == "skip_delete":
        return None
    if item["action"] == "execute":
        q = Path(item["query_file"]).read_text(encoding="utf-8").strip()
        return {"project_id": PROJECT_ID, "query": q, "meta": item}
    if item["action"] == "chunk":
        q = (REPO / item["path"]).read_text(encoding="utf-8")
        return {"project_id": PROJECT_ID, "query": q, "meta": item}
    raise ValueError(item)


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    state = load_progress()
    idx = state["index"]
    if cmd == "status":
        print(json.dumps({"index": idx, "total": len(plan), "done": state["done"]}))
        return 0
    if cmd == "next":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        out = []
        i = idx
        while len(out) < n and i < len(plan):
            item = plan[i]
            p = payload_for(item)
            if p is None:
                i += 1
                continue
            out.append(p)
            i += 1
        print(json.dumps(out, ensure_ascii=False))
        return 0
    if cmd == "advance":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        i = state["index"]
        advanced = 0
        while advanced < n and i < len(plan):
            i += 1
            advanced += 1
        state["index"] = i
        state["done"] = i
        save_progress(state)
        print(json.dumps({"index": i, "total": len(plan)}))
        return 0
    print("usage: next [N]|advance N|status", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Apply a range of prepared batch SQL files via stdin/stdout protocol for agent.

Prints lines: READY <step> <query_len>
Agent should execute SQL then call: python scripts/_mcp_apply_batch_range.py done <step>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "data" / "_mcp_batch" / "manifest.json"
STATE = REPO / "data" / "_mcp_batch_state.json"
PROJECT_ID = "vcojlixcuqinanjlflgd"


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"next_step": 0}


def save_state(st: dict) -> None:
    STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if len(sys.argv) >= 2 and sys.argv[1] == "done":
        step_name = sys.argv[2]
        st = load_state()
        st["next_step"] = int(step_name.split("_")[1]) + 1
        save_state(st)
        print(json.dumps({"advanced_to": st["next_step"]}))
        return 0
    if len(sys.argv) >= 2 and sys.argv[1] == "reset":
        save_state({"next_step": 0})
        return 0
    start = int(sys.argv[1]) if len(sys.argv) > 1 else load_state()["next_step"]
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    out = []
    for i in range(start, min(start + count, len(manifest))):
        entry = manifest[i]
        if entry.get("skip"):
            out.append({"step_i": i, "skip": True, "plan_index": entry["plan_index"]})
            continue
        sql = (REPO / entry["sql_file"]).read_text(encoding="utf-8")
        payload = {"project_id": PROJECT_ID, "query": sql, "meta": entry, "step_i": i}
        out.append(payload)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prepare current exec-plan step query for agent CallDynamicTool."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "data" / "_mcp_exec_plan.json"
PROGRESS = REPO / "data" / "_mcp_exec_progress.json"
QUERY_OUT = REPO / "data" / "_query_only.sql"
META_OUT = REPO / "data" / "_mcp_step_meta.json"
PROJECT_ID = "vcojlixcuqinanjlflgd"


def query_for(item: dict) -> str | None:
    if item["action"] == "skip_delete":
        return None
    if item["action"] == "execute":
        return Path(item["query_file"]).read_text(encoding="utf-8").strip()
    if item["action"] == "chunk":
        return (REPO / item["path"]).read_text(encoding="utf-8")
    raise ValueError(item)


def main() -> int:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    state = json.loads(PROGRESS.read_text(encoding="utf-8"))
    idx = state["index"]
    if idx >= len(plan):
        print(json.dumps({"action": "done", "index": idx, "total": len(plan)}))
        return 0
    item = plan[idx]
    q = query_for(item)
    if q is None:
        print(json.dumps({"action": "skip", "index": idx, "uid": item["uid"]}))
        return 0
    QUERY_OUT.write_text(q, encoding="utf-8")
    meta = {
        "action": "execute",
        "index": idx,
        "total": len(plan),
        "project_id": PROJECT_ID,
        "query_len": len(q),
        "uid": item.get("uid"),
        "chunk_i": item.get("chunk_i"),
        "label": item.get("label"),
    }
    META_OUT.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

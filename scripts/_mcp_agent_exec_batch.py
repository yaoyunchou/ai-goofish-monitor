#!/usr/bin/env python3
"""Prepare N exec-plan steps into data/_mcp_batch/ for agent MCP execution."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "data" / "_mcp_exec_plan.json"
PROGRESS = REPO / "data" / "_mcp_exec_progress.json"
OUT_DIR = REPO / "data" / "_mcp_batch"
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
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    state = json.loads(PROGRESS.read_text(encoding="utf-8"))
    idx = state["index"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    i = idx
    step = 0
    while step < n and i < len(plan):
        item = plan[i]
        q = query_for(item)
        entry = {"plan_index": i, "uid": item.get("uid"), "chunk_i": item.get("chunk_i"), "action": item["action"], "label": item.get("label")}
        if q is None:
            entry["skip"] = True
        else:
            sql_path = OUT_DIR / f"step_{step:03d}.sql"
            sql_path.write_text(q, encoding="utf-8")
            entry["sql_file"] = str(sql_path.relative_to(REPO)).replace("\\", "/")
            entry["query_len"] = len(q)
            entry["project_id"] = PROJECT_ID
        manifest.append(entry)
        i += 1
        step += 1
    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"start_index": idx, "prepared": len(manifest), "end_index": i, "manifest": str(manifest_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

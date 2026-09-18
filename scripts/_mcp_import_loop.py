#!/usr/bin/env python3
"""Prepare next MCP import step; agent calls execute_sql then re-runs with --mark."""
from __future__ import annotations

import json
import sys
from pathlib import Path

AGENT_TOOLS = Path(
    r"C:\Users\01848\.cursor\projects\d-work-work-2026-ai-goofish-monitor\agent-tools"
)
DATA = Path(__file__).resolve().parents[1] / "data"
PROGRESS = DATA / "mcp_import_progress.json"
PROJECT_ID = "vcojlixcuqinanjlflgd"

STEPS: list[tuple[str, str]] = [("sp:05", "sp_stmts/05.sql"), ("sp:06", "sp_stmts/06.sql")]
for i in range(1, 34):
    STEPS.append((str(i), f"import_{i:02d}"))


def load_query(arg: str) -> str:
    if arg.startswith("sp:"):
        return (AGENT_TOOLS / "sp_stmts" / f"{arg[3:]}.sql").read_text(encoding="utf-8")
    path = AGENT_TOOLS / f"mcp_call_{int(arg):02d}.json"
    return json.loads(path.read_text(encoding="utf-8"))["query"]


def load_progress() -> dict:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    return {"ok": [], "errors": [], "next_index": 0}


def save_progress(data: dict) -> None:
    PROGRESS.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    progress = load_progress()
    if len(sys.argv) > 1 and sys.argv[1] == "--mark":
        label = sys.argv[2]
        status = sys.argv[3]
        if status == "ok":
            progress["ok"].append(label)
        else:
            progress["errors"].append({"label": label, "error": sys.argv[4] if len(sys.argv) > 4 else "unknown"})
        progress["next_index"] = int(sys.argv[5]) if len(sys.argv) > 5 else progress.get("next_index", 0) + 1
        save_progress(progress)
        print(json.dumps({"marked": label, "status": status, "next_index": progress["next_index"]}))
        return 0

    idx = progress.get("next_index", 0)
    if idx >= len(STEPS):
        print(json.dumps({"done": True, "progress": progress}))
        return 0

    arg, label = STEPS[idx]
    query = load_query(arg)
    out = DATA / ".mcp_query.sql"
    out.write_text(query, encoding="utf-8")
    meta = {
        "project_id": PROJECT_ID,
        "label": label,
        "step_index": idx,
        "query_len": len(query),
        "query_file": str(out),
    }
    (DATA / ".mcp_step.meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

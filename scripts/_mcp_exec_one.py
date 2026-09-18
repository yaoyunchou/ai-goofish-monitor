#!/usr/bin/env python3
"""Print MCP execute_sql arguments JSON for a single import step."""
from __future__ import annotations

import json
import sys
from pathlib import Path

AGENT_TOOLS = Path(
    r"C:\Users\01848\.cursor\projects\d-work-work-2026-ai-goofish-monitor\agent-tools"
)
PROJECT_ID = "vcojlixcuqinanjlflgd"


def load_payload(arg: str) -> dict:
    if arg.startswith("sp:"):
        path = AGENT_TOOLS / "sp_stmts" / f"{arg[3:]}.sql"
        return {"project_id": PROJECT_ID, "query": path.read_text(encoding="utf-8"), "label": f"sp_stmts/{arg[3:]}.sql"}
    idx = int(arg)
    path = AGENT_TOOLS / f"mcp_call_{idx:02d}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["label"] = f"import_{idx:02d}"
    return payload


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _mcp_exec_one.py <index|sp:05>", file=sys.stderr)
        return 1
    payload = load_payload(sys.argv[1])
    sys.stdout.write(json.dumps({"project_id": payload["project_id"], "query": payload["query"], "label": payload["label"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

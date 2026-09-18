#!/usr/bin/env python3
"""Prepare SQL query for MCP execute_sql by label or import index."""
from __future__ import annotations

import json
import sys
from pathlib import Path

AGENT_TOOLS = Path(
    r"C:\Users\01848\.cursor\projects\d-work-work-2026-ai-goofish-monitor\agent-tools"
)
OUT = Path(__file__).resolve().parents[1] / "data" / ".mcp_query.sql"
PROJECT_ID = "vcojlixcuqinanjlflgd"


def load_query(arg: str) -> tuple[str, str]:
    if arg.startswith("sp:"):
        path = AGENT_TOOLS / "sp_stmts" / f"{arg[3:]}.sql"
        label = f"sp_stmts/{arg[3:]}.sql"
    elif arg.isdigit():
        idx = int(arg)
        path = AGENT_TOOLS / f"mcp_call_{idx:02d}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload["query"], f"import_{idx:02d}"
    else:
        path = Path(arg)
        label = path.name
    return path.read_text(encoding="utf-8"), label


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _prep_mcp_query.py <index|sp:05|path>", file=sys.stderr)
        return 1
    query, label = load_query(sys.argv[1])
    OUT.write_text(query, encoding="utf-8")
    meta = {"project_id": PROJECT_ID, "label": label, "query_len": len(query)}
    meta_path = OUT.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

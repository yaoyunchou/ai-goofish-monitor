#!/usr/bin/env python3
"""Load SQL query for MCP execute_sql by import index or file path."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AGENT_TOOLS = Path(
    r"C:\Users\01848\.cursor\projects\d-work-work-2026-ai-goofish-monitor\agent-tools"
)


def load_by_index(idx: int) -> str:
    path = AGENT_TOOLS / f"import_{idx:02d}.sql"
    if not path.exists():
        sys.path.insert(0, str(REPO))
        from scripts._run_supabase_import import collect_files

        files = collect_files()
        path = Path(files[idx]["path"])
    return path.read_text(encoding="utf-8")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _load_mcp_query.py <index|path>", file=sys.stderr)
        return 1
    arg = sys.argv[1]
    if arg.isdigit():
        query = load_by_index(int(arg))
    else:
        query = Path(arg).read_text(encoding="utf-8")
    payload = {"project_id": "vcojlixcuqinanjlflgd", "query": query}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Emit MCP execute_sql payloads one index at a time for agent-driven import."""
from __future__ import annotations

import json
import sys
from pathlib import Path

AGENT_TOOLS = Path(
    r"C:\Users\01848\.cursor\projects\d-work-work-2026-ai-goofish-monitor\agent-tools"
)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _mcp_import_executor.py <index>|count", file=sys.stderr)
        return 1
    if sys.argv[1] == "count":
        print(len(list(AGENT_TOOLS.glob("mcp_call_*.json"))))
        return 0
    idx = int(sys.argv[1])
    path = AGENT_TOOLS / f"mcp_call_{idx:02d}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    # stdout is consumed by agent for CallDynamicTool
    sys.stdout.write(payload["query"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

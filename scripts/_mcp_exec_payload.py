#!/usr/bin/env python3
"""Execute MCP payload from compact JSON file (project_id + query)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PAYLOAD = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    r"C:\Users\01848\AppData\Local\Cursor\AgentStores\cursor_agent_stores\c0286d5f-8364-45c1-b7fe-d0371fad8166\files\exec_payload.json"
)


def main() -> int:
    if not PAYLOAD.exists():
        print(json.dumps({"error": f"missing {PAYLOAD}"}), file=sys.stderr)
        return 1
    data = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    meta = {
        "project_id": data["project_id"],
        "query_len": len(data["query"]),
        "payload_path": str(PAYLOAD),
        "ready_for_mcp": True,
    }
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

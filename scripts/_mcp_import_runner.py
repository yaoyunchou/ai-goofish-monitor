#!/usr/bin/env python3
"""Run Supabase MCP execute_sql imports sequentially via prebuilt payloads."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

AGENT_TOOLS = Path(
    r"C:\Users\01848\.cursor\projects\d-work-work-2026-ai-goofish-monitor\agent-tools"
)
PROJECT_ID = "vcojlixcuqinanjlflgd"
PROGRESS = AGENT_TOOLS / "import_progress.json"


def _load_payload(idx: int) -> dict:
    path = AGENT_TOOLS / f"mcp_call_{idx:02d}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _save_progress(data: dict) -> None:
    PROGRESS.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> int:
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end = int(sys.argv[2]) if len(sys.argv) > 2 else 33
    progress = {"ok": [], "errors": [], "last_index": start - 1}
    if PROGRESS.exists():
        progress = json.loads(PROGRESS.read_text(encoding="utf-8"))

    for idx in range(start, end + 1):
        payload = _load_payload(idx)
        name = payload.get("name", f"mcp_call_{idx:02d}")
        print(f"[{idx:02d}] READY {name} query_len={len(payload['query'])}", flush=True)
        # Agent executes via CallDynamicTool; this script only emits metadata.
        progress["pending_index"] = idx
        _save_progress(progress)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

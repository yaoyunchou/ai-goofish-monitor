#!/usr/bin/env python3
"""Batch import via Supabase MCP execute_sql using streamable HTTP transport."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

AGENT_TOOLS = Path(
    r"C:\Users\01848\.cursor\projects\d-work-work-2026-ai-goofish-monitor\agent-tools"
)
DATA = Path(__file__).resolve().parents[1] / "data"
PROJECT_ID = "vcojlixcuqinanjlflgd"
MCP_URL = "https://mcp.supabase.com/mcp"
PROGRESS = DATA / "mcp_import_progress.json"

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


async def run_batch(start: int = 0) -> int:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    progress = load_progress()
    start = max(start, progress.get("next_index", 0))

    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for idx in range(start, len(STEPS)):
                arg, label = STEPS[idx]
                query = load_query(arg)
                try:
                    result = await session.call_tool(
                        "execute_sql",
                        {"project_id": PROJECT_ID, "query": query},
                    )
                    progress["ok"].append(label)
                    print(f"OK {label} len={len(query)}", flush=True)
                except Exception as exc:  # noqa: BLE001
                    progress["errors"].append({"label": label, "error": str(exc)})
                    print(f"ERR {label}: {exc}", flush=True)
                    progress["next_index"] = idx
                    save_progress(progress)
                    return 1
                progress["next_index"] = idx + 1
                save_progress(progress)

    print(json.dumps({"done": True, "progress": progress}, ensure_ascii=False))
    return 0


def main() -> int:
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    return asyncio.run(run_batch(start))


if __name__ == "__main__":
    raise SystemExit(main())

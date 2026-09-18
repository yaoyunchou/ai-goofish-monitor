#!/usr/bin/env python3
"""Run _mcp_exec_plan.json items sequentially via Supabase MCP HTTP (agent fallback).

Prints one line per item: OK|ERR <index> uid=<uid> action=<action> len=<len>
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "data" / "_mcp_exec_plan.json"
PROGRESS = REPO / "data" / "_mcp_exec_progress.json"
PROJECT_ID = "vcojlixcuqinanjlflgd"
MCP_URL = "https://mcp.supabase.com/mcp"


def load_progress() -> dict:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    return {"index": 0}


def save_progress(state: dict) -> None:
    PROGRESS.write_text(json.dumps(state, indent=2), encoding="utf-8")


def query_for(item: dict) -> str | None:
    if item["action"] == "skip_delete":
        return None
    if item["action"] == "execute":
        return Path(item["query_file"]).read_text(encoding="utf-8").strip()
    if item["action"] == "chunk":
        return (REPO / item["path"]).read_text(encoding="utf-8")
    raise ValueError(item)


async def run(start: int, limit: int) -> int:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    state = load_progress()
    idx = max(start, state["index"])
    done = 0
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            while idx < len(plan) and done < limit:
                item = plan[idx]
                q = query_for(item)
                if q is None:
                    print(f"SKIP {idx} uid={item['uid']} action=skip_delete")
                    idx += 1
                    done += 1
                    continue
                try:
                    await session.call_tool(
                        "execute_sql",
                        {"project_id": PROJECT_ID, "query": q},
                    )
                    print(
                        f"OK {idx} uid={item['uid']} action={item['action']} len={len(q)} label={item.get('label')}"
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"ERR {idx} uid={item['uid']} {exc}")
                    state["index"] = idx
                    save_progress(state)
                    return 1
                idx += 1
                done += 1
    state["index"] = idx
    state["done"] = idx
    save_progress(state)
    print(json.dumps({"index": idx, "total": len(plan), "batch_done": done}))
    return 0


def main() -> int:
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    return asyncio.run(run(start, limit))


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Load data/.invoke_args.json and call Supabase MCP execute_sql via stdio bridge.

Used when agent CallDynamicTool cannot inline large query payloads.
Requires Cursor MCP OAuth (works when plugin-supabase-supabase is authenticated).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

INVOKE = Path(__file__).resolve().parents[1] / "data" / ".invoke_args.json"
MCP_URL = "https://mcp.supabase.com/mcp"


async def run() -> int:
    if not INVOKE.exists():
        print(json.dumps({"error": f"missing {INVOKE}"}), file=sys.stderr)
        return 1
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    query = args["query"]
    project_id = args["project_id"]
    qlen = len(query)
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError as exc:
        print(json.dumps({"error": f"mcp package missing: {exc}"}), file=sys.stderr)
        return 1

    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "execute_sql",
                {"project_id": project_id, "query": query},
            )
    out = {"ok": True, "query_len": qlen, "result": str(result)}
    print(json.dumps(out, ensure_ascii=False))
    return 0


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())

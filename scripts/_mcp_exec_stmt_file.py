#!/usr/bin/env python3
"""Execute one SQL file via Supabase MCP streamable HTTP (requires Cursor OAuth cookies)."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

MCP_URL = "https://mcp.supabase.com/mcp"
PROJECT_ID = "vcojlixcuqinanjlflgd"


async def run(path: Path) -> dict:
    query = path.read_text(encoding="utf-8")
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "execute_sql",
                {"project_id": PROJECT_ID, "query": query},
            )
    return {"ok": True, "path": str(path), "query_len": len(query), "result": str(result)}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _mcp_exec_stmt_file.py <sql-file>", file=sys.stderr)
        return 1
    try:
        out = asyncio.run(run(Path(sys.argv[1])))
        print(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "path": sys.argv[1]}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

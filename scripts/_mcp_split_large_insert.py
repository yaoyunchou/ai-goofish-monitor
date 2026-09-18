#!/usr/bin/env python3
"""Split large INSERT (jsonb) into chunked MCP statements via _mcp_json_staging table."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHUNK_SIZE = 6000


def sql_escape(s: str) -> str:
    return s.replace("'", "''")


def split_insert(query: str, row_id: int, out_dir: Path) -> list[dict]:
    m = re.search(r", '(\{.*\})'::jsonb\);\s*$", query, re.DOTALL)
    if not m:
        raise ValueError("cannot parse raw_json from INSERT")
    raw_json = m.group(1)
    base_insert = query[: m.start()] + ", '{}'::jsonb);"

    stmts: list[str] = [
        "CREATE TABLE IF NOT EXISTS _mcp_json_staging (row_id int PRIMARY KEY, data text);",
        f"DELETE FROM _mcp_json_staging WHERE row_id = {row_id};",
        base_insert,
    ]
    chunks = [raw_json[i : i + CHUNK_SIZE] for i in range(0, len(raw_json), CHUNK_SIZE)]
    if chunks:
        stmts.append(
            f"INSERT INTO _mcp_json_staging (row_id, data) VALUES ({row_id}, '{sql_escape(chunks[0])}');"
        )
        for chunk in chunks[1:]:
            stmts.append(
                f"UPDATE _mcp_json_staging SET data = data || '{sql_escape(chunk)}' WHERE row_id = {row_id};"
            )
    stmts.append(
        f"UPDATE result_items SET raw_json = (SELECT data::jsonb FROM _mcp_json_staging WHERE row_id = {row_id}) WHERE id = {row_id};"
    )
    stmts.append(f"DELETE FROM _mcp_json_staging WHERE row_id = {row_id};")

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    for i, stmt in enumerate(stmts):
        p = out_dir / f"stmt_{i:02d}.sql"
        p.write_text(stmt, encoding="utf-8")
        manifest.append({"i": i, "len": len(stmt), "path": str(p.relative_to(REPO))})
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    query_file = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "data" / "_tool_query.txt"
    row_id = int(sys.argv[2]) if len(sys.argv) > 2 else 23
    out_dir = REPO / "data" / f"mcp_chunks_uid{row_id}"
    query = query_file.read_text(encoding="utf-8")
    manifest = split_insert(query, row_id, out_dir)
    print(
        json.dumps(
            {
                "row_id": row_id,
                "count": len(manifest),
                "max_len": max(x["len"] for x in manifest),
                "out_dir": str(out_dir.relative_to(REPO)),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

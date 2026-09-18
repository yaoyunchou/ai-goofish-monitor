#!/usr/bin/env python3
"""Load MCP execute_sql args from data/_ct_mcp_{N}.json and print metadata."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"


def main() -> int:
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    path = DATA / f"_ct_mcp_{idx}.json"
    if not path.exists():
        print(json.dumps({"error": f"missing {path}"}), file=sys.stderr)
        return 1
    args = json.loads(path.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "project_id": args["project_id"],
                "query_len": len(args["query"]),
                "query_file": str(DATA / f"_ct_part_{idx}.sql"),
                "invoke_json": str(path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

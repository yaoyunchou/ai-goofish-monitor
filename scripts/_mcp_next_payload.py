#!/usr/bin/env python3
"""Prepare next batch and emit invoke args metadata for agent MCP call."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INVOKE = REPO / "data" / ".invoke_args.json"
BATCH = REPO / "scripts" / "_mcp_batch_inserts.py"
QUEUE = REPO / "data" / "mcp_unit_queue.json"
LARGE = 30000


def main() -> int:
    st = json.loads(QUEUE.read_text(encoding="utf-8"))
    uid = st["next_uid"]
    if uid >= len(st["units"]):
        print(json.dumps({"action": "done"}))
        return 0
    unit = st["units"][uid]
    if unit["label"] in ("__count__", "__setval__"):
        query = Path(unit["query_file"]).read_text(encoding="utf-8").strip()
        payload = {"project_id": unit["project_id"], "query": query}
        INVOKE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        print(
            json.dumps(
                {
                    "action": "execute",
                    "mode": "special",
                    "uid": uid,
                    "label": unit["label"],
                    "query_len": len(query),
                    "invoke_path": str(INVOKE),
                    "project_id": unit["project_id"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    size = 1 if unit.get("query_len", 0) > LARGE else 3
    prep = json.loads(
        subprocess.check_output([sys.executable, str(BATCH), "prepare", str(size)], cwd=REPO).decode()
    )
    if prep.get("action") == "done":
        print(json.dumps(prep))
        return 0
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "action": "execute",
                "mode": "batch",
                **prep,
                "query_len": len(args["query"]),
                "invoke_path": str(INVOKE),
                "project_id": args["project_id"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

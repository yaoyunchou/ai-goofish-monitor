#!/usr/bin/env python3
"""Build execution plan for remaining MCP import units."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QUEUE = REPO / "data" / "mcp_unit_queue.json"
DELETE_SQL = "DELETE FROM result_items;"
MAX_SAFE = 8878
SPLIT = REPO / "scripts" / "_mcp_split_large_insert.py"


def main() -> int:
    start_uid = int(sys.argv[1]) if len(sys.argv) > 1 else 29
    state = json.loads(QUEUE.read_text(encoding="utf-8"))
    plan: list[dict] = []
    for u in state["units"]:
        uid = u["uid"]
        if uid < start_uid:
            continue
        q = Path(u["query_file"]).read_text(encoding="utf-8").strip()
        if q == DELETE_SQL and uid > 0:
            plan.append({"uid": uid, "action": "skip_delete", "label": u["label"]})
            continue
        if len(q) > MAX_SAFE and "'::jsonb)" in q:
            row_m = re.search(r"VALUES \((\d+),", q)
            row_id = int(row_m.group(1)) if row_m else uid
            out_dir = REPO / f"data/mcp_chunks_uid{row_id}"
            subprocess.run(
                [sys.executable, str(SPLIT), u["query_file"], str(row_id)],
                cwd=REPO,
                check=True,
            )
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            for m in manifest:
                plan.append(
                    {
                        "uid": uid,
                        "action": "chunk",
                        "chunk_i": m["i"],
                        "len": m["len"],
                        "path": m["path"],
                        "label": u["label"],
                    }
                )
        else:
            plan.append(
                {
                    "uid": uid,
                    "action": "execute",
                    "len": len(q),
                    "label": u["label"],
                    "query_file": u["query_file"],
                }
            )
    out = REPO / "data" / "_mcp_exec_plan.json"
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"plan_items": len(plan), "by_action": dict(Counter(p["action"] for p in plan))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run _mcp_exec_plan.json steps via psycopg until result_items COUNT target."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import psycopg

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "data" / "_mcp_exec_plan.json"
PROGRESS = REPO / "data" / "_mcp_exec_progress.json"


def db_url() -> str:
    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                raw = line.split("=", 1)[1].strip()
                break
    return raw.replace("postgresql+asyncpg://", "postgresql://")


def load_progress() -> dict:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    return {"index": 0, "done": 0}


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


def count_items(cur) -> int:
    cur.execute("SELECT COUNT(*) FROM result_items")
    return cur.fetchone()[0]


def main() -> int:
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 47
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    state = load_progress()
    idx = state["index"]
    executed = 0

    with psycopg.connect(db_url()) as conn:
        with conn.cursor() as cur:
            while idx < len(plan):
                cur.execute("SELECT COUNT(*) FROM result_items")
                if cur.fetchone()[0] >= target:
                    break
                item = plan[idx]
                q = query_for(item)
                if q is not None:
                    cur.execute(q)
                    executed += 1
                idx += 1
                state["index"] = idx
                state["done"] = idx
                save_progress(state)
                conn.commit()

            cur.execute(
                "SELECT COUNT(*) AS cnt, COUNT(*) FILTER (WHERE length(raw_json::text) > 1000) AS good FROM result_items"
            )
            cnt, good = cur.fetchone()

    print(json.dumps({"index": idx, "total": len(plan), "executed": executed, "cnt": cnt, "good": good}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Emit import plan: all SQL steps for Supabase MCP execute_sql (agent-driven)."""
from __future__ import annotations

import json
from pathlib import Path

AGENT_TOOLS = Path(
    r"C:\Users\01848\.cursor\projects\d-work-work-2026-ai-goofish-monitor\agent-tools"
)
REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
PROJECT_ID = "vcojlixcuqinanjlflgd"

# User-requested order
STEPS: list[tuple[str, Path]] = [
    ("seller_profiles.sql", REPO / "data" / "pg_migration" / "tables" / "seller_profiles.sql"),
]
for i in range(1, 17):
    STEPS.append(
        (
            f"result_items/{i:03d}.sql",
            REPO / "data" / "pg_migration" / "tables" / "chunks" / "result_items" / f"{i:03d}.sql",
        )
    )
for i in range(1, 18):
    STEPS.append(
        (
            f"price_snapshots/{i:03d}.sql",
            REPO / "data" / "pg_migration" / "tables" / "chunks" / "price_snapshots" / f"{i:03d}.sql",
        )
    )


def main() -> int:
    plan = []
    for label, path in STEPS:
        if not path.exists():
            plan.append({"label": label, "error": f"missing {path}"})
            continue
        query = path.read_text(encoding="utf-8")
        payload = {"project_id": PROJECT_ID, "query": query}
        out = DATA / f".mcp_step_{len(plan):03d}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        plan.append({"index": len(plan), "label": label, "query_len": len(query), "payload": str(out)})
    (DATA / "mcp_import_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"steps": len(plan), "plan": DATA / "mcp_import_plan.json"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

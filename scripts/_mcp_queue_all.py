#!/usr/bin/env python3
"""Build full MCP unit queue from remaining import steps (split large SQL)."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
AGENT_TOOLS = Path(
    r"C:\Users\01848\.cursor\projects\d-work-work-2026-ai-goofish-monitor\agent-tools"
)
PROJECT_ID = "vcojlixcuqinanjlflgd"
PROGRESS = DATA / "mcp_import_progress.json"
QUEUE = DATA / "mcp_unit_queue.json"
UNITS_DIR = DATA / "mcp_units"
MAX_FULL = 65536

STEPS: list[tuple[str, str]] = [("sp:05", "sp_stmts/05.sql"), ("sp:06", "sp_stmts/06.sql")]
for i in range(1, 34):
    STEPS.append((str(i), f"import_{i:02d}"))


def split_sql(query: str) -> list[str]:
    parts = re.split(r";\s*\n", query.strip())
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if not p.endswith(";"):
            p += ";"
        out.append(p)
    return out


def load_query(arg: str) -> str:
    if arg.startswith("sp:"):
        return (AGENT_TOOLS / "sp_stmts" / f"{arg[3:]}.sql").read_text(encoding="utf-8")
    path = AGENT_TOOLS / f"mcp_call_{int(arg):02d}.json"
    return json.loads(path.read_text(encoding="utf-8"))["query"]


def main() -> int:
    progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
    start = progress.get("next_index", 0)
    UNITS_DIR.mkdir(parents=True, exist_ok=True)
    units: list[dict] = []
    uid = 0
    for idx in range(start, len(STEPS)):
        arg, label = STEPS[idx]
        query = load_query(arg)
        stmts = split_sql(query) if len(query) > MAX_FULL else [query]
        for si, stmt in enumerate(stmts):
            qpath = UNITS_DIR / f"unit_{uid:04d}.sql"
            qpath.write_text(stmt, encoding="utf-8")
            units.append(
                {
                    "uid": uid,
                    "step_index": idx,
                    "label": label,
                    "stmt_index": si,
                    "stmt_total": len(stmts),
                    "is_last_stmt_of_step": si == len(stmts) - 1,
                    "next_index_after_step": idx + 1,
                    "project_id": PROJECT_ID,
                    "query_file": str(qpath),
                    "query_len": len(stmt),
                    "query_sha256": hashlib.sha256(stmt.encode()).hexdigest(),
                }
            )
            uid += 1
    # count + setval as final units
    count_sql = (
        "SELECT 'app_metadata' AS t, COUNT(*) FROM app_metadata\n"
        "UNION ALL SELECT 'tasks', COUNT(*) FROM tasks\n"
        "UNION ALL SELECT 'result_items', COUNT(*) FROM result_items\n"
        "UNION ALL SELECT 'price_snapshots', COUNT(*) FROM price_snapshots\n"
        "UNION ALL SELECT 'seller_profiles', COUNT(*) FROM seller_profiles\n"
        "UNION ALL SELECT 'seller_subscriptions', COUNT(*) FROM seller_subscriptions\n"
        "UNION ALL SELECT 'seller_item_metrics', COUNT(*) FROM seller_item_metrics;"
    )
    setval_sql = (
        "SELECT setval('result_items_id_seq', COALESCE((SELECT MAX(id) FROM result_items), 1), (SELECT COUNT(*) > 0 FROM result_items));\n"
        "SELECT setval('price_snapshots_id_seq', COALESCE((SELECT MAX(id) FROM price_snapshots), 1), (SELECT COUNT(*) > 0 FROM price_snapshots));\n"
        "SELECT setval('seller_profiles_id_seq', COALESCE((SELECT MAX(id) FROM seller_profiles), 1), (SELECT COUNT(*) > 0 FROM seller_profiles));"
    )
    for name, sql in [("__count__", count_sql), ("__setval__", setval_sql)]:
        qpath = UNITS_DIR / f"unit_{uid:04d}.sql"
        qpath.write_text(sql, encoding="utf-8")
        units.append(
            {
                "uid": uid,
                "step_index": None,
                "label": name,
                "stmt_index": 0,
                "stmt_total": 1,
                "is_last_stmt_of_step": True,
                "next_index_after_step": None,
                "project_id": PROJECT_ID,
                "query_file": str(qpath),
                "query_len": len(sql),
                "query_sha256": hashlib.sha256(sql.encode()).hexdigest(),
            }
        )
        uid += 1
    state = {"next_uid": 0, "done_uids": [], "units": units}
    QUEUE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"total_units": len(units), "from_step_index": start, "queue": str(QUEUE)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

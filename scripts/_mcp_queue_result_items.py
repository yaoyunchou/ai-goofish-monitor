#!/usr/bin/env python3
"""Build MCP unit queue for result_items chunks only (pg_migration source).

Use when price_snapshots/seller_profiles are already imported but result_items
was cleared (e.g. by DELETE in a later chunk).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
CHUNKS = DATA / "pg_migration" / "tables" / "chunks" / "result_items"
UNITS_DIR = DATA / "mcp_units"
QUEUE = DATA / "mcp_unit_queue.json"
PROGRESS = DATA / "mcp_import_progress.json"
PROJECT_ID = "vcojlixcuqinanjlflgd"


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


def main() -> int:
    chunk_files = sorted(CHUNKS.glob("*.sql"))
    if not chunk_files:
        print(f"no chunks in {CHUNKS}", file=sys.stderr)
        return 1

    UNITS_DIR.mkdir(parents=True, exist_ok=True)
    units: list[dict] = []
    uid = 0
    for ci, chunk_path in enumerate(chunk_files):
        label = f"result_items/{chunk_path.name}"
        query = chunk_path.read_text(encoding="utf-8")
        stmts = split_sql(query)
        for si, stmt in enumerate(stmts):
            qpath = UNITS_DIR / f"ri_{uid:04d}.sql"
            qpath.write_text(stmt, encoding="utf-8")
            units.append(
                {
                    "uid": uid,
                    "step_index": ci,
                    "label": label,
                    "stmt_index": si,
                    "stmt_total": len(stmts),
                    "is_last_stmt_of_step": si == len(stmts) - 1,
                    "next_index_after_step": ci + 1,
                    "project_id": PROJECT_ID,
                    "query_file": str(qpath),
                    "query_len": len(stmt),
                    "query_sha256": hashlib.sha256(stmt.encode()).hexdigest(),
                }
            )
            uid += 1

    count_sql = (
        "SELECT 'app_metadata' AS t, COUNT(*)::int FROM app_metadata\n"
        "UNION ALL SELECT 'tasks', COUNT(*)::int FROM tasks\n"
        "UNION ALL SELECT 'result_items', COUNT(*)::int FROM result_items\n"
        "UNION ALL SELECT 'price_snapshots', COUNT(*)::int FROM price_snapshots\n"
        "UNION ALL SELECT 'seller_subscriptions', COUNT(*)::int FROM seller_subscriptions\n"
        "UNION ALL SELECT 'seller_item_metrics', COUNT(*)::int FROM seller_item_metrics\n"
        "UNION ALL SELECT 'seller_profiles', COUNT(*)::int FROM seller_profiles\n"
        "ORDER BY t;"
    )
    setval_sql = (
        "SELECT setval('result_items_id_seq', (SELECT COALESCE(MAX(id), 1) FROM result_items));\n"
        "SELECT setval('price_snapshots_id_seq', (SELECT COALESCE(MAX(id), 1) FROM price_snapshots));\n"
        "SELECT setval('seller_profiles_id_seq', (SELECT COALESCE(MAX(id), 1) FROM seller_profiles));"
    )
    for extra_label, extra_sql in [("__count__", count_sql), ("__setval__", setval_sql)]:
        qpath = UNITS_DIR / f"ri_{uid:04d}.sql"
        qpath.write_text(extra_sql, encoding="utf-8")
        units.append(
            {
                "uid": uid,
                "step_index": None,
                "label": extra_label,
                "stmt_index": 0,
                "stmt_total": 1,
                "is_last_stmt_of_step": True,
                "next_index_after_step": None,
                "project_id": PROJECT_ID,
                "query_file": str(qpath),
                "query_len": len(extra_sql),
                "query_sha256": hashlib.sha256(extra_sql.encode()).hexdigest(),
            }
        )
        uid += 1

    queue = {"next_uid": 0, "done_uids": [], "units": units}
    QUEUE.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")

    progress = {
        "ok": [],
        "errors": [],
        "next_index": 0,
        "manifest": "result_items chunks only",
        "total_units": len(units),
        "note": "Rebuilt after result_items cleared; price_snapshots import skipped",
    }
    PROGRESS.write_text(json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({"units": len(units), "chunks": len(chunk_files), "queue": str(QUEUE)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

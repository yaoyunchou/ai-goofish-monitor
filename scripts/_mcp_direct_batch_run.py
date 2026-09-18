#!/usr/bin/env python3
"""Execute remaining mcp_unit_queue batches via direct PostgreSQL (batch prepare/done workflow).

Usage:
  python scripts/_mcp_direct_batch_run.py run
  python scripts/_mcp_direct_batch_run.py verify
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
INVOKE = DATA / ".invoke_args.json"
QUEUE = DATA / "mcp_unit_queue.json"
BATCH = REPO / "scripts" / "_mcp_batch_inserts.py"
RUN_UNIT = REPO / "scripts" / "_mcp_run_unit.py"
ENV = REPO / ".env"
LARGE_THRESHOLD = 30000
DEFAULT_BATCH = 3
PROJECT_ID = "vcojlixcuqinanjlflgd"


def load_env_database_url() -> str:
    text = ENV.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip()
            return re.sub(r"^postgresql\+asyncpg://", "postgresql://", url)
    raise SystemExit("DATABASE_URL not found in .env")


def prepare_batch(size: int) -> dict:
    return json.loads(
        subprocess.check_output([sys.executable, str(BATCH), "prepare", str(size)], cwd=REPO).decode()
    )


def mark_done() -> dict:
    return json.loads(subprocess.check_output([sys.executable, str(BATCH), "done"], cwd=REPO).decode())


def mark_unit_done(uid: int) -> dict:
    return json.loads(
        subprocess.check_output([sys.executable, str(RUN_UNIT), "done"], cwd=REPO).decode()
    )


def execute_query(conn, query: str) -> None:
    with conn.cursor() as cur:
        cur.execute(query)


def run_all() -> dict:
    import psycopg2

    url = load_env_database_url()
    errors: list[dict] = []
    executed_batches = 0
    executed_units = 0

    conn = psycopg2.connect(url)
    conn.autocommit = True
    try:
        while True:
            state = json.loads(QUEUE.read_text(encoding="utf-8"))
            uid = state["next_uid"]
            if uid >= len(state["units"]):
                break
            unit = state["units"][uid]
            if unit["label"] in ("__count__", "__setval__"):
                break

            batch_size = 1 if unit.get("query_len", 0) > LARGE_THRESHOLD else DEFAULT_BATCH
            prep = prepare_batch(batch_size)
            if prep.get("action") == "done":
                break

            args = json.loads(INVOKE.read_text(encoding="utf-8"))
            try:
                execute_query(conn, args["query"])
                mark_done()
                executed_batches += 1
                executed_units += prep.get("stmt_count", 0)
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    {
                        "merged_uids": prep.get("merged_uids"),
                        "error": str(exc),
                    }
                )
                break

        # uid 63 __count__ and 64 __setval__
        state = json.loads(QUEUE.read_text(encoding="utf-8"))
        for special_uid in (63, 64):
            if special_uid in state["done_uids"]:
                continue
            if state["next_uid"] != special_uid:
                continue
            unit = state["units"][special_uid]
            query = Path(unit["query_file"]).read_text(encoding="utf-8").strip()
            payload = {"project_id": PROJECT_ID, "query": query}
            INVOKE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            try:
                execute_query(conn, query)
                mark_unit_done(special_uid)
            except Exception as exc:  # noqa: BLE001
                errors.append({"uid": special_uid, "label": unit["label"], "error": str(exc)})
    finally:
        conn.close()

    return {
        "executed_batches": executed_batches,
        "executed_units": executed_units,
        "errors": errors,
        "queue_status": json.loads(QUEUE.read_text(encoding="utf-8")),
    }


def verify() -> dict:
    import psycopg2

    url = load_env_database_url()
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT "
                "(SELECT count(*)::int FROM result_items) AS result_items, "
                "(SELECT count(*)::int FROM price_snapshots) AS price_snapshots, "
                "(SELECT count(*)::int FROM seller_profiles) AS seller_profiles"
            )
            row = cur.fetchone()
            return {
                "result_items": row[0],
                "price_snapshots": row[1],
                "seller_profiles": row[2],
            }
    finally:
        conn.close()


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        print(json.dumps(run_all(), ensure_ascii=False, indent=2))
        return 0
    if cmd == "verify":
        print(json.dumps(verify(), ensure_ascii=False, indent=2))
        return 0
    print("usage: run|verify", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Batch next N INSERT units (skip DELETE) into one invoke payload for single MCP call.

Usage:
  python scripts/_mcp_batch_inserts.py prepare 5
  # CallDynamicTool execute_sql with json.load(data/.invoke_args.json)
  python scripts/_mcp_batch_inserts.py done
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
INVOKE = DATA / ".invoke_args.json"
QUEUE = DATA / "mcp_unit_queue.json"
BATCH_STATE = DATA / ".mcp_batch_state.json"
RUN = REPO / "scripts" / "_mcp_run_unit.py"
APPLY = REPO / "scripts" / "_mcp_apply_invoke.py"
DELETE_SQL = "DELETE FROM result_items;"


def load_queue() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def save_queue(state: dict) -> None:
    QUEUE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def prepare_batch(max_inserts: int) -> dict:
    state = load_queue()
    uid = state["next_uid"]
    if uid >= len(state["units"]):
        return {"action": "done", "next_uid": uid}

    merged_uids: list[int] = []
    skipped_delete: list[int] = []
    queries: list[str] = []
    project_id = state["units"][uid]["project_id"]

    while len(queries) < max_inserts and uid < len(state["units"]):
        unit = state["units"][uid]
        if unit["label"] in ("__count__", "__setval__"):
            break
        query = Path(unit["query_file"]).read_text(encoding="utf-8").strip()
        if query == DELETE_SQL and uid > 0:
            state["done_uids"].append(uid)
            skipped_delete.append(uid)
            uid += 1
            state["next_uid"] = uid
            save_queue(state)
            continue
        merged_uids.append(uid)
        queries.append(query)
        uid += 1

    if not queries:
        return {"action": "done", "next_uid": load_queue()["next_uid"], "skipped_delete_uids": skipped_delete}

    combined = "\n".join(queries)
    payload = {"project_id": project_id, "query": combined}
    INVOKE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    check = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
    batch = {
        "merged_uids": merged_uids,
        "skipped_delete_uids": skipped_delete,
        "query_len": check["query_len"],
        "query_sha256": check["query_sha256"],
        "stmt_count": len(queries),
    }
    BATCH_STATE.write_text(json.dumps(batch, indent=2), encoding="utf-8")
    return {"action": "execute", **batch, "project_id": project_id}


def mark_batch_done() -> dict:
    batch = json.loads(BATCH_STATE.read_text(encoding="utf-8"))
    state = load_queue()
    marked: list[int] = []
    for uid in batch["merged_uids"]:
        unit = state["units"][uid]
        state["done_uids"].append(uid)
        state["next_uid"] = uid + 1
        if unit.get("step_index") is not None and unit.get("is_last_stmt_of_step"):
            subprocess.check_call(
                [
                    sys.executable,
                    str(REPO / "scripts" / "_mcp_sequential_import.py"),
                    "--mark",
                    unit["label"],
                    "ok",
                    str(unit["next_index_after_step"]),
                ],
                cwd=REPO,
            )
        marked.append(uid)
        save_queue(state)
        state = load_queue()
    BATCH_STATE.unlink(missing_ok=True)
    return {"marked_uids": marked, "next_uid": load_queue()["next_uid"]}


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    if cmd == "prepare":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        print(json.dumps(prepare_batch(n), ensure_ascii=False))
        return 0
    if cmd == "done":
        print(json.dumps(mark_batch_done(), ensure_ascii=False))
        return 0
    print("usage: prepare [N]|done", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

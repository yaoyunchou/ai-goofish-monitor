#!/usr/bin/env python3
"""Prepare MCP payloads for all remaining import steps (agent calls execute_sql per step)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
PROGRESS = DATA / "mcp_import_progress.json"
PAYLOAD = DATA / ".mcp_step_payload.json"
SEQUENTIAL = REPO / "scripts" / "_mcp_sequential_import.py"
APPLY = REPO / "scripts" / "_mcp_apply_invoke.py"


def load_progress() -> dict:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    return {"ok": [], "errors": [], "next_index": 0}


def prepare_one() -> dict:
    out = subprocess.check_output([sys.executable, str(SEQUENTIAL)], text=True, encoding="utf-8")
    meta = json.loads(out.strip().splitlines()[-1])
    check = subprocess.check_output([sys.executable, str(APPLY), "--check"], text=True, encoding="utf-8")
    check_meta = json.loads(check.strip())
    invoke = json.loads((DATA / ".invoke_args.json").read_text(encoding="utf-8"))
    assert len(invoke["query"]) == check_meta["query_len"], (
        f"query_len mismatch: {len(invoke['query'])} vs {check_meta['query_len']}"
    )
    payload = {"project_id": invoke["project_id"], "query": invoke["query"], "label": meta["label"]}
    PAYLOAD.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return {
        "label": meta["label"],
        "step_index": meta["step_index"],
        "query_len": len(invoke["query"]),
        "query_sha256": check_meta["query_sha256"],
        "payload_path": str(PAYLOAD),
    }


def mark_ok(label: str, next_index: int) -> None:
    subprocess.check_call(
        [sys.executable, str(SEQUENTIAL), "--mark", label, "ok", str(next_index)],
    )


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "prepare":
        progress = load_progress()
        idx = progress.get("next_index", 0)
        if idx >= 35:
            print(json.dumps({"done": True, "progress": progress}, ensure_ascii=False))
            return 0
        info = prepare_one()
        info["next_index"] = idx
        print(json.dumps(info, ensure_ascii=False))
        return 0
    if len(sys.argv) > 3 and sys.argv[1] == "mark":
        mark_ok(sys.argv[2], int(sys.argv[3]))
        print(json.dumps({"marked": sys.argv[2], "next_index": int(sys.argv[3])}))
        return 0
    print("usage: _mcp_run_all_steps.py prepare | mark <label> <next_index>", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

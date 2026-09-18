#!/usr/bin/env python3
"""Orchestrate remaining MCP import: prepare units, track stmt progress, emit next payload."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
INVOKE = DATA / ".invoke_args.json"
PROGRESS = DATA / "mcp_import_progress.json"
WORK = DATA / ".mcp_work"
STATE = DATA / ".mcp_full_import_state.json"
SEQ = REPO / "scripts" / "_mcp_sequential_import.py"
APPLY = REPO / "scripts" / "_mcp_apply_invoke.py"
PROJECT_ID = "vcojlixcuqinanjlflgd"
MAX_FULL = 65536


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


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def prepare_step() -> dict:
    subprocess.run([sys.executable, str(SEQ)], check=True, cwd=REPO)
    check = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    qlen = len(args["query"])
    if check["query_len"] != qlen:
        raise SystemExit(f"query_len mismatch check={check['query_len']} actual={qlen}")
    progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
    idx = progress["next_index"]
    seq_out = json.loads(subprocess.check_output([sys.executable, str(SEQ)], cwd=REPO).decode())
    label = seq_out["label"]
    if qlen <= MAX_FULL:
        save_state({"mode": "full", "label": label, "step_index": idx, "next_index": idx + 1})
        return {
            "action": "execute",
            "mode": "full",
            "label": label,
            "step_index": idx,
            "next_index_after_ok": idx + 1,
            "project_id": PROJECT_ID,
            "query_len": qlen,
            "query_sha256": check["query_sha256"],
            "invoke_path": str(INVOKE),
        }
    stmts = split_sql(args["query"])
    step_dir = WORK / f"step_{idx:02d}_{label.replace('/', '_')}"
    step_dir.mkdir(parents=True, exist_ok=True)
    stmt_paths: list[str] = []
    for i, stmt in enumerate(stmts):
        p = step_dir / f"stmt_{i:03d}.sql"
        p.write_text(stmt, encoding="utf-8")
        stmt_paths.append(str(p))
    state = load_state()
    done: list[str] = state.get("done_stmts", []) if state.get("label") == label else []
    pending = [p for p in stmt_paths if p not in done]
    if not pending:
        save_state({"mode": "mark", "label": label, "step_index": idx, "next_index": idx + 1})
        return {"action": "mark", "label": label, "next_index": idx + 1, "step_index": idx}
    stmt_path = pending[0]
    query = Path(stmt_path).read_text(encoding="utf-8")
    payload = {"project_id": PROJECT_ID, "query": query}
    INVOKE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    check2 = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
    save_state(
        {
            "mode": "split",
            "label": label,
            "step_index": idx,
            "next_index": idx + 1,
            "done_stmts": done,
            "current_stmt": stmt_path,
            "stmt_total": len(stmt_paths),
        }
    )
    return {
        "action": "execute",
        "mode": "stmt",
        "label": label,
        "step_index": idx,
        "stmt_path": stmt_path,
        "stmt_index": stmt_paths.index(stmt_path),
        "stmt_total": len(stmt_paths),
        "stmt_remaining": len(pending),
        "project_id": PROJECT_ID,
        "query_len": check2["query_len"],
        "query_sha256": check2["query_sha256"],
        "invoke_path": str(INVOKE),
    }


def mark_stmt_done(stmt_path: str) -> dict:
    state = load_state()
    done = state.get("done_stmts", [])
    if stmt_path not in done:
        done.append(stmt_path)
    state["done_stmts"] = done
    save_state(state)
    return {"stmt_done": stmt_path, "done_count": len(done)}


def mark_step(label: str, next_index: int) -> dict:
    subprocess.check_call([sys.executable, str(SEQ), "--mark", label, "ok", str(next_index)], cwd=REPO)
    if STATE.exists():
        STATE.unlink()
    return json.loads(PROGRESS.read_text(encoding="utf-8"))


def status() -> dict:
    progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
    state = load_state()
    return {"progress": progress, "state": state}


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "next"
    if cmd == "next":
        print(json.dumps(prepare_step(), ensure_ascii=False))
        return 0
    if cmd == "verify":
        args = json.loads(INVOKE.read_text(encoding="utf-8"))
        print(len(args["query"]))
        return 0
    if cmd == "stmt-done" and len(sys.argv) > 2:
        print(json.dumps(mark_stmt_done(sys.argv[2]), ensure_ascii=False))
        return 0
    if cmd == "mark" and len(sys.argv) > 3:
        print(json.dumps(mark_step(sys.argv[2], int(sys.argv[3])), ensure_ascii=False))
        return 0
    if cmd == "status":
        print(json.dumps(status(), ensure_ascii=False))
        return 0
    print("usage: next|verify|stmt-done <path>|mark <label> <next_index>|status", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

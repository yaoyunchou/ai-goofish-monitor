#!/usr/bin/env python3
"""Prepare next MCP unit (full query or stmt) for agent CallDynamicTool.

Usage:
  python scripts/_mcp_agent_loop.py next          # write data/.invoke_args.json
  python scripts/_mcp_agent_loop.py verify      # print query_len for check
  python scripts/_mcp_agent_loop.py mark <label> <next_index>
  python scripts/_mcp_agent_loop.py status
"""
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


def load_progress() -> dict:
    return json.loads(PROGRESS.read_text(encoding="utf-8"))


def prepare_step() -> dict:
    subprocess.run([sys.executable, str(SEQ)], check=True, cwd=REPO)
    check = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    qlen = len(args["query"])
    if check["query_len"] != qlen:
        raise SystemExit(f"query_len mismatch check={check['query_len']} actual={qlen}")
    progress = load_progress()
    idx = progress["next_index"]
    label = json.loads(subprocess.check_output([sys.executable, str(SEQ)], cwd=REPO).decode())["label"]
    state_path = DATA / ".mcp_agent_loop_state.json"
    if qlen <= MAX_FULL:
        state = {"mode": "full", "label": label, "step_index": idx, "next_index": idx + 1, "stmt_index": None}
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        return {
            "mode": "full",
            "label": label,
            "step_index": idx,
            "next_index_after_ok": idx + 1,
            "project_id": PROJECT_ID,
            "query_len": qlen,
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
    done_path = DATA / ".mcp_agent_loop_done.json"
    done: list[str] = []
    if done_path.exists():
        done = json.loads(done_path.read_text(encoding="utf-8"))
    pending = [p for p in stmt_paths if p not in done]
    if not pending:
        state = {"mode": "mark_ready", "label": label, "step_index": idx, "next_index": idx + 1}
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        return {"mode": "mark_ready", "label": label, "next_index": idx + 1, "query_len": qlen}
    stmt_path = pending[0]
    query = Path(stmt_path).read_text(encoding="utf-8")
    payload = {"project_id": PROJECT_ID, "query": query}
    INVOKE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    state = {
        "mode": "stmt",
        "label": label,
        "step_index": idx,
        "next_index": idx + 1,
        "stmt_path": stmt_path,
        "stmt_remaining": len(pending),
    }
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return {
        "mode": "stmt",
        "label": label,
        "step_index": idx,
        "stmt_path": stmt_path,
        "project_id": PROJECT_ID,
        "query_len": len(query),
        "stmt_remaining": len(pending),
        "invoke_path": str(INVOKE),
    }


def mark_stmt_done(stmt_path: str) -> None:
    done_path = DATA / ".mcp_agent_loop_done.json"
    done: list[str] = []
    if done_path.exists():
        done = json.loads(done_path.read_text(encoding="utf-8"))
    if stmt_path not in done:
        done.append(stmt_path)
    done_path.write_text(json.dumps(done, indent=2), encoding="utf-8")


def mark_step(label: str, next_index: int) -> dict:
    subprocess.check_call([sys.executable, str(SEQ), "--mark", label, "ok", str(next_index)], cwd=REPO)
    for p in [DATA / ".mcp_agent_loop_state.json", DATA / ".mcp_agent_loop_done.json"]:
        if p.exists():
            p.unlink()
    return load_progress()


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
        mark_stmt_done(sys.argv[2])
        print(json.dumps({"stmt_done": sys.argv[2]}, ensure_ascii=False))
        return 0
    if cmd == "mark" and len(sys.argv) > 3:
        print(json.dumps(mark_step(sys.argv[2], int(sys.argv[3])), ensure_ascii=False))
        return 0
    if cmd == "status":
        print(PROGRESS.read_text(encoding="utf-8"))
        return 0
    print("usage: next|verify|stmt-done <path>|mark <label> <next_index>|status", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

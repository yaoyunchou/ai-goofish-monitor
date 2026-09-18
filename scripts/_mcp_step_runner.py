#!/usr/bin/env python3
"""Orchestrate MCP import steps: prepare, list stmts, mark progress.

Agent loop:
  python scripts/_mcp_step_runner.py next          # prepare + print action
  # CallDynamicTool execute_sql (full query or each stmt)
  python scripts/_mcp_step_runner.py mark-ok       # mark current step ok
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
PROGRESS = DATA / "mcp_import_progress.json"
INVOKE = DATA / ".invoke_args.json"
SEQ = REPO / "scripts" / "_mcp_sequential_import.py"
APPLY = REPO / "scripts" / "_mcp_apply_invoke.py"
AUTO = REPO / "scripts" / "_mcp_auto_runner.py"
STATE = DATA / ".mcp_step_runner_state.json"
PROJECT_ID = "vcojlixcuqinanjlflgd"


def split_sql(query: str) -> list[str]:
    import re

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


def prepare_current() -> dict:
    subprocess.run([sys.executable, str(SEQ)], check=True, cwd=REPO)
    meta = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    qlen = len(args["query"])
    if meta["query_len"] != qlen:
        raise SystemExit(f"query_len mismatch check={meta['query_len']} actual={qlen}")
    progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
    idx = progress["next_index"]
    label = json.loads(subprocess.check_output([sys.executable, str(SEQ)], cwd=REPO).decode())["label"]
    stmts = split_sql(args["query"])
    step_dir = DATA / ".mcp_work" / f"step_{idx:02d}_{label.replace('/', '_')}"
    step_dir.mkdir(parents=True, exist_ok=True)
    stmt_paths: list[str] = []
    for i, stmt in enumerate(stmts):
        p = step_dir / f"stmt_{i:03d}.sql"
        p.write_text(stmt, encoding="utf-8")
        stmt_paths.append(str(p))
    state = {
        "step_index": idx,
        "label": label,
        "next_index_after_ok": idx + 1,
        "project_id": PROJECT_ID,
        "query_len": qlen,
        "query_sha256": hashlib.sha256(args["query"].encode()).hexdigest(),
        "use_full_query": qlen <= 65536,
        "stmt_paths": stmt_paths,
        "stmt_lens": [len(s) for s in stmts],
        "stmt_done": [],
    }
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    return state


def load_state() -> dict:
    if not STATE.exists():
        return prepare_current()
    return json.loads(STATE.read_text(encoding="utf-8"))


def next_action() -> dict:
    state = load_state()
    pending = [p for p in state["stmt_paths"] if p not in state.get("stmt_done", [])]
    if pending:
        path = pending[0]
        query = Path(path).read_text(encoding="utf-8")
        return {
            "mode": "stmt",
            "label": state["label"],
            "step_index": state["step_index"],
            "project_id": state["project_id"],
            "query": query,
            "query_len": len(query),
            "stmt_path": path,
            "stmt_remaining": len(pending),
        }
    # all stmts done for step
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    return {
        "mode": "mark_ready",
        "label": state["label"],
        "next_index": state["next_index_after_ok"],
        "query_len": state["query_len"],
        "project_id": args["project_id"],
    }


def mark_stmt_done(path: str) -> dict:
    state = load_state()
    done = state.setdefault("stmt_done", [])
    if path not in done:
        done.append(path)
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    return state


def mark_step_ok() -> dict:
    state = load_state()
    subprocess.check_call(
        [sys.executable, str(SEQ), "--mark", state["label"], "ok", str(state["next_index_after_ok"])],
        cwd=REPO,
    )
    if STATE.exists():
        STATE.unlink()
    progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
    return progress


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "next"
    if cmd == "prepare":
        print(json.dumps(prepare_current(), ensure_ascii=False))
        return 0
    if cmd == "next":
        action = next_action()
        # Don't dump full query in stdout for huge payloads; agent uses json.load invoke_args
        if action.get("mode") == "stmt" and action["query_len"] > 2000:
            slim = {k: v for k, v in action.items() if k != "query"}
            slim["query_file"] = action["stmt_path"]
            print(json.dumps(slim, ensure_ascii=False))
        else:
            print(json.dumps(action, ensure_ascii=False))
        return 0
    if cmd == "stmt-done" and len(sys.argv) > 2:
        print(json.dumps(mark_stmt_done(sys.argv[2]), ensure_ascii=False))
        return 0
    if cmd == "mark-ok":
        print(json.dumps(mark_step_ok(), ensure_ascii=False))
        return 0
    if cmd == "status":
        print(PROGRESS.read_text(encoding="utf-8"))
        return 0
    print("usage: prepare|next|stmt-done <path>|mark-ok|status", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

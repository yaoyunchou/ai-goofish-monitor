#!/usr/bin/env python3
"""Run remaining MCP import units; prints one execute unit at a time for agent CallDynamicTool.

After agent executes execute_sql, run:
  python scripts/_mcp_run_loop.py done
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
STATE = DATA / ".mcp_run_loop_state.json"
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


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def prepare_full_step() -> dict:
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
    save_state({"mode": "full", "label": label, "step_index": idx, "next_index": idx + 1})
    return {
        "action": "execute",
        "label": label,
        "step_index": idx,
        "next_index_after_ok": idx + 1,
        "project_id": PROJECT_ID,
        "query_len": qlen,
        "query_sha256": check["query_sha256"],
        "invoke_path": str(INVOKE),
    }


def prepare_split_step() -> dict:
    state = load_state()
    progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
    idx = progress["next_index"]
    seq_out = json.loads(subprocess.check_output([sys.executable, str(SEQ)], cwd=REPO).decode())
    label = seq_out["label"]
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    qlen = len(args["query"])
    stmts = split_sql(args["query"])
    step_dir = WORK / f"step_{idx:02d}_{label.replace('/', '_')}"
    step_dir.mkdir(parents=True, exist_ok=True)
    stmt_paths: list[str] = []
    for i, stmt in enumerate(stmts):
        p = step_dir / f"stmt_{i:03d}.sql"
        p.write_text(stmt, encoding="utf-8")
        stmt_paths.append(str(p))
    done = state.get("done_stmts", []) if state.get("label") == label else []
    pending = [p for p in stmt_paths if p not in done]
    if not pending:
        save_state({"mode": "mark", "label": label, "step_index": idx, "next_index": idx + 1})
        return {"action": "mark", "label": label, "next_index": idx + 1, "step_index": idx}
    stmt_path = pending[0]
    query = Path(stmt_path).read_text(encoding="utf-8")
    payload = {"project_id": PROJECT_ID, "query": query}
    INVOKE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    check = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
    save_state(
        {
            "mode": "split",
            "label": label,
            "step_index": idx,
            "next_index": idx + 1,
            "done_stmts": done,
            "stmt_paths": stmt_paths,
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
        "query_len": check["query_len"],
        "query_sha256": check["query_sha256"],
        "invoke_path": str(INVOKE),
    }


def next_unit() -> dict:
    progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
    if progress["next_index"] >= 35:
        return {"action": "done", "progress": progress}
    state = load_state()
    if state.get("mode") == "split" and state.get("label"):
        return prepare_split_step()
    subprocess.run([sys.executable, str(SEQ)], check=True, cwd=REPO)
    check = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    qlen = len(args["query"])
    if check["query_len"] != qlen:
        raise SystemExit(f"query_len mismatch check={check['query_len']} actual={qlen}")
    if qlen <= MAX_FULL:
        progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
        idx = progress["next_index"]
        seq_out = json.loads(subprocess.check_output([sys.executable, str(SEQ)], cwd=REPO).decode())
        label = seq_out["label"]
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
    return prepare_split_step()


def mark_done() -> dict:
    state = load_state()
    if state.get("mode") == "split":
        stmt_paths = state.get("stmt_paths", [])
        done = state.get("done_stmts", [])
        pending = [p for p in stmt_paths if p not in done]
        if pending:
            done.append(pending[0])
            state["done_stmts"] = done
            save_state(state)
            remaining = [p for p in stmt_paths if p not in done]
            if remaining:
                return {"action": "continue_split", "done": pending[0], "remaining": len(remaining)}
        label = state["label"]
        next_index = state["next_index"]
        subprocess.check_call([sys.executable, str(SEQ), "--mark", label, "ok", str(next_index)], cwd=REPO)
        if STATE.exists():
            STATE.unlink()
        return {"action": "marked", "label": label, "next_index": next_index}
    if state.get("mode") == "full":
        label = state["label"]
        next_index = state["next_index"]
        subprocess.check_call([sys.executable, str(SEQ), "--mark", label, "ok", str(next_index)], cwd=REPO)
        if STATE.exists():
            STATE.unlink()
        return {"action": "marked", "label": label, "next_index": next_index}
    raise SystemExit("no pending state; run next first")


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "next"
    if cmd == "next":
        print(json.dumps(next_unit(), ensure_ascii=False))
        return 0
    if cmd == "done":
        print(json.dumps(mark_done(), ensure_ascii=False))
        return 0
    if cmd == "verify":
        args = json.loads(INVOKE.read_text(encoding="utf-8"))
        print(len(args["query"]))
        return 0
    if cmd == "status":
        print(json.dumps({"progress": json.loads(PROGRESS.read_text()), "state": load_state()}, ensure_ascii=False))
        return 0
    print("usage: next|done|verify|status", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prepare import steps and split large SQL into statement files for MCP execute_sql."""
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


def split_sql(query: str) -> list[str]:
    """Split on semicolon-newline boundaries (safe for our migration chunks)."""
    parts = re.split(r";\s*\n", query.strip())
    stmts: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if not p.endswith(";"):
            p += ";"
        stmts.append(p)
    return stmts


STEPS: list[tuple[str, str]] = [("sp:05", "sp_stmts/05.sql"), ("sp:06", "sp_stmts/06.sql")]
for _i in range(1, 34):
    STEPS.append((str(_i), f"import_{_i:02d}"))


def prepare_step() -> dict:
    progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
    idx = progress["next_index"]
    if idx >= len(STEPS):
        return {"done": True, "progress": progress}
    label = STEPS[idx][1]
    subprocess.run([sys.executable, str(SEQ)], check=True, cwd=REPO)
    check = json.loads(subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=REPO).decode())
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    qlen = len(args["query"])
    if check["query_len"] != qlen:
        raise SystemExit(f"query_len mismatch: {check['query_len']} vs {qlen}")
    stmts = split_sql(args["query"])
    step_dir = WORK / f"step_{idx:02d}_{label.replace('/', '_')}"
    step_dir.mkdir(parents=True, exist_ok=True)
    stmt_paths: list[str] = []
    for i, stmt in enumerate(stmts):
        p = step_dir / f"stmt_{i:03d}.sql"
        p.write_text(stmt, encoding="utf-8")
        stmt_paths.append(str(p))
    meta = {
        "step_index": idx,
        "label": label,
        "next_index_after_ok": idx + 1,
        "project_id": PROJECT_ID,
        "query_len": qlen,
        "query_sha256": hashlib.sha256(args["query"].encode()).hexdigest(),
        "stmt_count": len(stmts),
        "stmt_paths": stmt_paths,
        "stmt_lens": [len(s) for s in stmts],
        "full_query_path": str(INVOKE),
        "use_full_query": qlen <= 65536,
    }
    (step_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def mark_ok(label: str, next_index: int) -> None:
    subprocess.check_call([sys.executable, str(SEQ), "--mark", label, "ok", str(next_index)], cwd=REPO)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "prepare":
        print(json.dumps(prepare_step(), ensure_ascii=False))
        return 0
    if len(sys.argv) > 3 and sys.argv[1] == "mark":
        mark_ok(sys.argv[2], int(sys.argv[3]))
        print(json.dumps({"marked": sys.argv[2], "next_index": int(sys.argv[3])}))
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(PROGRESS.read_text(encoding="utf-8"))
        return 0
    print("usage: prepare | mark <label> <next_index> | status", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

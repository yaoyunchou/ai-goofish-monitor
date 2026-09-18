#!/usr/bin/env python3
"""Prepare next step and write MCP payload to agent store via json.load(invoke_args)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEQ = ROOT / "scripts" / "_mcp_sequential_import.py"
APPLY = ROOT / "scripts" / "_mcp_apply_invoke.py"
INVOKE = ROOT / "data" / ".invoke_args.json"
AGENT_STORE = Path(
    r"C:\Users\01848\AppData\Local\Cursor\AgentStores\cursor_agent_stores\c0286d5f-8364-45c1-b7fe-d0371fad8166\files"
)
OUT = AGENT_STORE / "mcp_call.json"


def main() -> int:
    subprocess.run(
        [sys.executable, str(SEQ)],
        check=True,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    meta = json.loads(
        subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=ROOT).decode()
    )
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    qlen = len(args["query"])
    if meta["query_len"] != qlen:
        print(json.dumps({"error": "query_len mismatch", "meta": meta, "actual": qlen}), file=sys.stderr)
        return 1
    sha = hashlib.sha256(args["query"].encode("utf-8")).hexdigest()
    if meta["query_sha256"] != sha:
        print(json.dumps({"error": "sha256 mismatch", "meta": meta["query_sha256"], "actual": sha}), file=sys.stderr)
        return 1
    AGENT_STORE.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"project_id": args["project_id"], "query": args["query"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    progress = json.loads((ROOT / "data" / "mcp_import_progress.json").read_text(encoding="utf-8"))
    idx = progress.get("next_index", 0)
    labels = ["sp_stmts/05.sql", "sp_stmts/06.sql"] + [f"import_{i:02d}" for i in range(1, 34)]
    print(
        json.dumps(
            {
                "step_index": idx,
                "label": labels[idx] if idx < len(labels) else f"step_{idx}",
                "query_len": qlen,
                "query_sha256": sha,
                "mcp_call_path": str(OUT),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

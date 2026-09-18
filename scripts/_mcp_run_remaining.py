#!/usr/bin/env python3
"""Prepare one import step; agent calls execute_sql then marks ok."""
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
PROGRESS = ROOT / "data" / "mcp_import_progress.json"


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
        print(json.dumps(progress, ensure_ascii=False))
        return 0

    subprocess.run([sys.executable, str(SEQ)], check=True, cwd=ROOT)
    meta_raw = subprocess.check_output([sys.executable, str(APPLY), "--check"], cwd=ROOT)
    meta = json.loads(meta_raw.decode("utf-8"))
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    qlen = len(args["query"])
    if meta["query_len"] != qlen:
        print(json.dumps({"error": "query_len mismatch", "meta": meta, "actual": qlen}), file=sys.stderr)
        return 1
    progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
    idx = progress.get("next_index", 0)
    labels = [("sp_stmts/05.sql", 0), ("sp_stmts/06.sql", 1)] + [
        (f"import_{i:02d}", i + 1) for i in range(1, 34)
    ]
    label = labels[idx][0] if idx < len(labels) else f"step_{idx}"
    out = {
        "step_index": idx,
        "label": label,
        "next_index_after_ok": idx + 1,
        "project_id": args["project_id"],
        "query_len": qlen,
        "query_sha256": hashlib.sha256(args["query"].encode("utf-8")).hexdigest(),
        "invoke_path": str(INVOKE),
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

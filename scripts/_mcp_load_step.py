#!/usr/bin/env python3
"""Load one import step into data/.invoke_args.json from pg_migration or agent-tools payloads."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
AGENT_TOOLS = Path(
    r"C:\Users\01848\.cursor\projects\d-work-work-2026-ai-goofish-monitor\agent-tools"
)
PROJECT_ID = "vcojlixcuqinanjlflgd"
INVOKE = DATA / ".invoke_args.json"

# User order: seller_profiles.sql, result_items 001-016, price_snapshots 001-017
USER_STEPS: list[Path] = [REPO / "data/pg_migration/tables/seller_profiles.sql"]
USER_STEPS += sorted((REPO / "data/pg_migration/tables/chunks/result_items").glob("*.sql"))
USER_STEPS += sorted((REPO / "data/pg_migration/tables/chunks/price_snapshots").glob("*.sql"))


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"steps": len(USER_STEPS)}, ensure_ascii=False))
        return 0
    idx = int(sys.argv[1])
    if idx < 0 or idx >= len(USER_STEPS):
        print(json.dumps({"error": f"index out of range 0..{len(USER_STEPS)-1}"}), file=sys.stderr)
        return 1
    path = USER_STEPS[idx]
    if not path.exists():
        print(json.dumps({"error": f"missing {path}"}), file=sys.stderr)
        return 1
    query = path.read_text(encoding="utf-8")
    payload = {"project_id": PROJECT_ID, "query": query}
    INVOKE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "index": idx,
                "label": str(path.relative_to(REPO)).replace("\\", "/"),
                "query_len": len(query),
                "invoke": str(INVOKE),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

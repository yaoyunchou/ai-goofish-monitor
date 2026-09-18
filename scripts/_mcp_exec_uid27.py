#!/usr/bin/env python3
"""Load invoke_args and print MCP args JSON for agent CallDynamicTool (uid 27)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

INVOKE = Path(__file__).resolve().parents[1] / "data" / ".invoke_args.json"


def main() -> int:
    args = json.loads(INVOKE.read_text(encoding="utf-8"))
    payload = {"project_id": args["project_id"], "query": args["query"]}
    assert len(payload["query"]) == 32006
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Load MCP execute_sql arguments from data/.invoke_args.json to stdout (UTF-8, no BOM)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

INVOKE = Path(__file__).resolve().parents[1] / "data" / ".invoke_args.json"


def main() -> int:
    if not INVOKE.exists():
        print(f"missing {INVOKE}", file=sys.stderr)
        return 1
    payload = json.loads(INVOKE.read_text(encoding="utf-8"))
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

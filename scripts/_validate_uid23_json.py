"""Validate assembled JSON from uid 23 chunk files."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNK_DIR = ROOT / "data" / "mcp_chunks_uid23"


def main() -> None:
    parts: list[str] = []
    for i in range(3, 9):
        sql = (CHUNK_DIR / f"stmt_{i:02d}.sql").read_text(encoding="utf-8")
        if i == 3:
            m = re.search(r"VALUES \(23, '(.+)'\);", sql, re.S)
        else:
            m = re.search(r"data \|\| '(.+)' WHERE", sql, re.S)
        if not m:
            raise SystemExit(f"chunk {i}: pattern not found")
        parts.append(m.group(1))

    full = "".join(parts)
    print("assembled_len", len(full))
    try:
        obj = json.loads(full)
        print("json_ok", True)
        print("keys", list(obj.keys()))
    except json.JSONDecodeError as exc:
        print("json_ok", False, exc)
        start = max(0, exc.pos - 80)
        print("context", repr(full[start : exc.pos + 80]))


if __name__ == "__main__":
    main()

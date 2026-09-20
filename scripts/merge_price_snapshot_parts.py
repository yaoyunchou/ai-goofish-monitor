#!/usr/bin/env python3
"""合并 MCP 分片导出并写入 data/db_sync_snapshot/price_snapshots.json"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
OUT = _REPO / "data" / "db_sync_snapshot" / "price_snapshots.json"


def extract(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    m = re.search(r'\[\{"rows":(\[.*\])\}\]', text, re.DOTALL)
    if not m:
        raise ValueError(path)
    return json.loads(m.group(1))


def main() -> int:
    base = _REPO / "data" / "mcp_exports"
    p1 = base / "price_part1.txt"
    p2 = base / "price_part2.txt"
    if not p1.is_file() or not p2.is_file():
        print("缺少 data/mcp_exports/price_part*.txt", file=sys.stderr)
        return 1
    rows = extract(p1) + extract(p2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    print(f"price_snapshots: {len(rows)} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

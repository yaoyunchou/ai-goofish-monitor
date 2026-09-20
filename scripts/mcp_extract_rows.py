#!/usr/bin/env python3
"""解析 Supabase MCP execute_sql 导出文件，提取 rows JSON 数组。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def extract_rows(text: str) -> list[dict]:
    try:
        outer = json.loads(text)
        if isinstance(outer, dict) and "result" in outer:
            text = str(outer["result"])
    except json.JSONDecodeError:
        pass

    m = re.search(r'\[\{"rows":(\[.*\])\}\]', text, re.DOTALL)
    if m:
        return json.loads(m.group(1))

    m = re.search(r'\[\{"payload":\[\{"rows":(\[.*\])\}\]\}\]', text, re.DOTALL)
    if m:
        return json.loads(m.group(1))

    start = text.find('[{"row_to_json"')
    if start >= 0:
        end = text.rfind("]", start)
        if end > start:
            arr = json.loads(text[start : end + 1])
            return [item["row_to_json"] for item in arr if "row_to_json" in item]

    raise ValueError("未找到 rows JSON")


def main() -> int:
    if len(sys.argv) < 3:
        print("用法: python mcp_extract_rows.py <mcp_export.txt> <out.json>", file=sys.stderr)
        return 1
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    rows = extract_rows(src.read_text(encoding="utf-8"))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    print(f"写入 {len(rows)} 行 -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""从 Supabase MCP base64 导出文件解码为表 JSON 快照。"""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path


def decode_mcp_b64_export(text: str) -> list[dict]:
    try:
        outer = json.loads(text)
        if isinstance(outer, dict) and "result" in outer:
            text = str(outer["result"])
    except json.JSONDecodeError:
        pass

    m = re.search(r'\[\{"b64":"([^"]+)"\}\]', text, re.DOTALL)
    if not m:
        raise ValueError("未找到 b64 字段")
    raw = m.group(1).replace("\\n", "")
    payload = base64.b64decode(raw).decode("utf-8")
    rows = json.loads(payload)
    if not isinstance(rows, list):
        raise ValueError("解码结果不是数组")
    return rows


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "用法: python decode_mcp_b64_export.py <mcp_export.txt> <out.json>",
            file=sys.stderr,
        )
        return 1
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    rows = decode_mcp_b64_export(src.read_text(encoding="utf-8"))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    print(f"写入 {len(rows)} 行 -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

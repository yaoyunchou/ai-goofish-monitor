#!/usr/bin/env python3
"""将 data/pg_migration/tables/chunks 下的 SQL 导入目标库。

需要环境变量 TARGET_DATABASE_URL（新加坡项目连接串）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
CHUNKS_DIR = _REPO_ROOT / "data" / "pg_migration" / "tables" / "chunks"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--target-url", default=None)
    args = parser.parse_args()

    import os
    import re

    import psycopg

    target = args.target_url or os.environ.get("TARGET_DATABASE_URL", "")
    target = re.sub(r"^postgresql\+asyncpg://", "postgresql://", target.strip())
    target = re.sub(r"^postgresql\+psycopg://", "postgresql://", target)
    if not target:
        print("请设置 TARGET_DATABASE_URL 或 --target-url", file=sys.stderr)
        return 1

    chunk_dir = CHUNKS_DIR / args.table
    if not chunk_dir.is_dir():
        print(f"无 chunk 目录: {chunk_dir}", file=sys.stderr)
        return 1

    files = sorted(chunk_dir.glob("*.sql"))
    print(f"导入 {args.table}: {len(files)} 个 chunk …")
    with psycopg.connect(target, connect_timeout=20) as conn:
        for path in files:
            sql = path.read_text(encoding="utf-8")
            conn.execute(sql)
            conn.commit()
            print(f"  OK {path.name} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

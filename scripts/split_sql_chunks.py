#!/usr/bin/env python3
"""将大 SQL 文件按 INSERT 语句拆成多个 chunk 文件。"""
from __future__ import annotations

import sys
from pathlib import Path

TABLE = sys.argv[1] if len(sys.argv) > 1 else "result_items"
CHUNK_SIZE = int(sys.argv[2]) if len(sys.argv) > 2 else 5

src = Path(__file__).resolve().parents[1] / "data" / "pg_migration" / "tables" / f"{TABLE}.sql"
out_dir = src.parent / "chunks" / TABLE
out_dir.mkdir(parents=True, exist_ok=True)

lines = src.read_text(encoding="utf-8").splitlines()
header = []
inserts = []
for line in lines:
    if line.startswith("DELETE"):
        header.append(line)
    elif line.startswith("INSERT"):
        inserts.append(line)

chunks = []
if header:
    batch = header.copy()
else:
    batch = []
for ins in inserts:
    batch.append(ins)
    if len(batch) >= CHUNK_SIZE + len(header):
        chunks.append(batch)
        batch = header.copy()
if batch and (not header or len(batch) > len(header)):
    chunks.append(batch)

for i, chunk in enumerate(chunks, 1):
    path = out_dir / f"{i:03d}.sql"
    path.write_text("\n".join(chunk) + "\n", encoding="utf-8")
    print(path.name, path.stat().st_size)

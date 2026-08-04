"""
结果文件命名等与存储相关的常量（主库为 PostgreSQL）。
"""
from __future__ import annotations

# 仅 scripts/migrate_sqlite_to_postgres 读取旧文件时的默认路径
LEGACY_SQLITE_MIGRATION_SOURCE = "data/app.sqlite3"

RESULT_FILE_SUFFIX = "_full_data.jsonl"


def build_result_filename(keyword: str) -> str:
    return f"{str(keyword or '').replace(' ', '_')}{RESULT_FILE_SUFFIX}"


def normalize_keyword_from_filename(filename: str) -> str:
    return str(filename or "").replace(RESULT_FILE_SUFFIX, "")


def normalize_keyword_slug(keyword: str) -> str:
    text = "".join(
        char for char in str(keyword or "").lower().replace(" ", "_")
        if char.isalnum() or char in "_-"
    ).rstrip("_")
    return text or "unknown"

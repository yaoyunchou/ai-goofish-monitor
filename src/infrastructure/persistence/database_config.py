"""
数据库驱动与连接串配置。
"""
from __future__ import annotations

import os
import re
from functools import lru_cache


DRIVER_SQLITE = "sqlite"
DRIVER_POSTGRES = "postgres"


@lru_cache(maxsize=1)
def get_database_driver() -> str:
    raw = (os.getenv("DATABASE_DRIVER") or DRIVER_SQLITE).strip().lower()
    if raw in {DRIVER_POSTGRES, "postgresql", "supabase"}:
        return DRIVER_POSTGRES
    return DRIVER_SQLITE


def is_postgres() -> bool:
    return get_database_driver() == DRIVER_POSTGRES


def get_sqlite_database_path() -> str:
    from src.infrastructure.persistence.storage_names import DEFAULT_DATABASE_PATH

    return os.getenv("APP_DATABASE_FILE", DEFAULT_DATABASE_PATH)


def get_postgres_dsn() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_DRIVER=postgres 时必须设置 DATABASE_URL（见 docs/database-supabase-integration.md）"
        )
    # SQLAlchemy 风格前缀转为 psycopg 可识别的 postgresql://
    url = re.sub(r"^postgresql\+asyncpg://", "postgresql://", url, count=1)
    url = re.sub(r"^postgresql\+psycopg://", "postgresql://", url, count=1)
    if not url.startswith("postgresql://"):
        raise RuntimeError("DATABASE_URL 必须以 postgresql:// 或 postgresql+asyncpg:// 开头")
    return url

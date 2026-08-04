"""
PostgreSQL（Supabase）连接配置。
"""
from __future__ import annotations

import re

from src.infrastructure.config.env_manager import env_manager

DRIVER_POSTGRES = "postgres"


def _config_value(key: str) -> str | None:
    value = env_manager.get_value(key)
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def is_postgres() -> bool:
    return True


def get_database_driver() -> str:
    """兼容旧调用；运行库固定为 Postgres。"""
    return DRIVER_POSTGRES


def get_postgres_dsn() -> str:
    url = (_config_value("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError(
            "必须设置 DATABASE_URL（Supabase Session pooler 连接串，见 docs/database-supabase-integration.md）"
        )
    url = re.sub(r"^postgresql\+asyncpg://", "postgresql://", url, count=1)
    url = re.sub(r"^postgresql\+psycopg://", "postgresql://", url, count=1)
    if not url.startswith("postgresql://"):
        raise RuntimeError("DATABASE_URL 必须以 postgresql:// 或 postgresql+asyncpg:// 开头")
    return url

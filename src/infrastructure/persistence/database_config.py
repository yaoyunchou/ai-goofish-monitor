"""
数据库驱动与连接串配置。

与 Web 设置、runtime_status 一致：通过 env_manager 解析配置，
仓库内 `.env` 优先于进程环境变量（含 Cursor Cloud Secrets），避免云端旧 Secret 覆盖本机已更新的连接串。
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

from src.infrastructure.config.env_manager import env_manager


DRIVER_SQLITE = "sqlite"
DRIVER_POSTGRES = "postgres"


def _config_value(key: str, default: Optional[str] = None) -> Optional[str]:
    value = env_manager.get_value(key, default)
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


@lru_cache(maxsize=1)
def get_database_driver() -> str:
    raw = (_config_value("DATABASE_DRIVER", DRIVER_SQLITE) or DRIVER_SQLITE).lower()
    if raw in {DRIVER_POSTGRES, "postgresql", "supabase"}:
        return DRIVER_POSTGRES
    return DRIVER_SQLITE


def is_postgres() -> bool:
    return get_database_driver() == DRIVER_POSTGRES


def get_sqlite_database_path() -> str:
    from src.infrastructure.persistence.storage_names import DEFAULT_DATABASE_PATH

    return _config_value("APP_DATABASE_FILE", DEFAULT_DATABASE_PATH) or DEFAULT_DATABASE_PATH


def get_postgres_dsn() -> str:
    url = (_config_value("DATABASE_URL") or "").strip()
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

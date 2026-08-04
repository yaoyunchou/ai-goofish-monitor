"""数据库连接配置（Postgres）。

SQLite 已完全移除，应用只支持 Postgres（含 Supabase）。
与 Web 设置、runtime_status 一致：通过 env_manager 解析配置，
仓库内 `.env` 优先于进程环境变量（含 Cursor Cloud Secrets），避免云端旧 Secret 覆盖本机已更新的连接串。
连接串通过 `DATABASE_URL` 提供。
"""
from __future__ import annotations

import re
from typing import Optional

from src.infrastructure.config.env_manager import env_manager


DRIVER_POSTGRES = "postgres"


def _config_value(key: str, default: Optional[str] = None) -> Optional[str]:
    value = env_manager.get_value(key, default)
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def get_database_driver() -> str:
    """当前唯一支持的驱动：Postgres。"""
    return DRIVER_POSTGRES


def is_postgres() -> bool:
    return True


def get_postgres_dsn() -> str:
    url = (_config_value("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError(
            "必须设置 DATABASE_URL（Postgres 连接串，见 docs/database-supabase-integration.md）"
        )
    # SQLAlchemy 风格前缀转为 psycopg 可识别的 postgresql://
    url = re.sub(r"^postgresql\+asyncpg://", "postgresql://", url, count=1)
    url = re.sub(r"^postgresql\+psycopg://", "postgresql://", url, count=1)
    if not url.startswith("postgresql://"):
        raise RuntimeError("DATABASE_URL 必须以 postgresql:// 或 postgresql+asyncpg:// 开头")
    return url

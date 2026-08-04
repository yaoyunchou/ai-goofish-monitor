"""数据库连接配置测试（Postgres-only，env_manager 解析）。"""
from __future__ import annotations

import pytest

from src.infrastructure.config.env_manager import EnvManager
from src.infrastructure.config import env_manager as env_manager_module
from src.infrastructure.persistence.database_config import (
    DRIVER_POSTGRES,
    get_database_driver,
    get_postgres_dsn,
    is_postgres,
)


@pytest.fixture()
def isolated_env_manager(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    manager = EnvManager(str(env_file))
    monkeypatch.setattr(env_manager_module, "env_manager", manager)
    monkeypatch.setattr(
        "src.infrastructure.persistence.database_config.env_manager",
        manager,
    )
    yield manager


def test_driver_is_always_postgres(isolated_env_manager):
    assert get_database_driver() == DRIVER_POSTGRES
    assert is_postgres() is True


def test_normalize_asyncpg_dsn(isolated_env_manager, monkeypatch):
    isolated_env_manager.env_file.write_text(
        "DATABASE_URL=postgresql+asyncpg://postgres:secret@db.example.com:5432/postgres\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:wrong@db.example.com:5432/postgres",
    )
    assert get_postgres_dsn() == "postgresql://postgres:secret@db.example.com:5432/postgres"


def test_normalize_psycopg_dsn(isolated_env_manager, monkeypatch):
    isolated_env_manager.env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://postgres:secret@db.example.com:5432/postgres\n",
        encoding="utf-8",
    )
    assert get_postgres_dsn() == "postgresql://postgres:secret@db.example.com:5432/postgres"


def test_env_file_preferred_over_process_env_for_dsn(isolated_env_manager, monkeypatch):
    isolated_env_manager.env_file.write_text(
        "DATABASE_URL=postgresql://postgres:from-file@db.example.com:5432/postgres\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://postgres:from-process@db.example.com:5432/postgres",
    )
    assert get_postgres_dsn() == "postgresql://postgres:from-file@db.example.com:5432/postgres"


def test_dsn_requires_url(isolated_env_manager, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_postgres_dsn()


def test_dsn_rejects_non_postgres_scheme(isolated_env_manager, monkeypatch):
    isolated_env_manager.env_file.write_text(
        "DATABASE_URL=mysql://user:pass@host/db\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="postgresql"):
        get_postgres_dsn()

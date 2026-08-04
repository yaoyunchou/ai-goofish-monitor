"""Postgres 连接串与驱动检测。"""
from __future__ import annotations

import pytest

from src.infrastructure.config.env_manager import EnvManager
from src.infrastructure.config import env_manager as env_manager_module
from src.infrastructure.persistence.database_config import (
    DRIVER_POSTGRES,
    DRIVER_SQLITE,
    get_database_driver,
    get_postgres_dsn,
    is_postgres,
)


@pytest.fixture()
def isolated_env_manager(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_DRIVER=sqlite\n", encoding="utf-8")
    manager = EnvManager(str(env_file))
    monkeypatch.setattr(env_manager_module, "env_manager", manager)
    monkeypatch.setattr(
        "src.infrastructure.persistence.database_config.env_manager",
        manager,
    )
    get_database_driver.cache_clear()
    yield manager
    get_database_driver.cache_clear()


def test_default_driver_sqlite(isolated_env_manager):
    assert get_database_driver() == DRIVER_SQLITE
    assert is_postgres() is False


def test_postgres_driver_aliases(isolated_env_manager):
    isolated_env_manager.env_file.write_text("DATABASE_DRIVER=supabase\n", encoding="utf-8")
    get_database_driver.cache_clear()
    assert get_database_driver() == DRIVER_POSTGRES


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


def test_env_file_preferred_over_process_env_for_driver(isolated_env_manager, monkeypatch):
    isolated_env_manager.env_file.write_text("DATABASE_DRIVER=sqlite\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_DRIVER", "postgres")
    get_database_driver.cache_clear()
    assert get_database_driver() == DRIVER_SQLITE


def test_postgres_dsn_requires_url(isolated_env_manager, monkeypatch):
    isolated_env_manager.env_file.write_text(
        "DATABASE_DRIVER=postgres\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_database_driver.cache_clear()
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_postgres_dsn()

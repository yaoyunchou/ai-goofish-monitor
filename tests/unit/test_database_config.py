"""Postgres 连接串配置。"""
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
    env_file.write_text(
        "DATABASE_URL=postgresql+asyncpg://postgres:secret@db.example.com:5432/postgres\n",
        encoding="utf-8",
    )
    manager = EnvManager(str(env_file))
    monkeypatch.setattr(env_manager_module, "env_manager", manager)
    monkeypatch.setattr(
        "src.infrastructure.persistence.database_config.env_manager",
        manager,
    )
    yield manager


def test_always_postgres(isolated_env_manager):
    assert is_postgres() is True
    assert get_database_driver() == DRIVER_POSTGRES


def test_normalize_asyncpg_dsn(isolated_env_manager, monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:wrong@db.example.com:5432/postgres",
    )
    assert get_postgres_dsn() == "postgresql://postgres:secret@db.example.com:5432/postgres"


def test_postgres_dsn_requires_url(isolated_env_manager, monkeypatch):
    isolated_env_manager.env_file.write_text("\n", encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_postgres_dsn()

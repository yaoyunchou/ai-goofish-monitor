"""Postgres 连接串与驱动检测。"""
from __future__ import annotations

import os

import pytest

from src.infrastructure.persistence.database_config import (
    DRIVER_POSTGRES,
    DRIVER_SQLITE,
    get_database_driver,
    get_postgres_dsn,
    is_postgres,
)


def test_default_driver_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_DRIVER", raising=False)
    get_database_driver.cache_clear()
    assert get_database_driver() == DRIVER_SQLITE
    assert is_postgres() is False


def test_postgres_driver_aliases(monkeypatch):
    monkeypatch.setenv("DATABASE_DRIVER", "supabase")
    get_database_driver.cache_clear()
    assert get_database_driver() == DRIVER_POSTGRES


def test_normalize_asyncpg_dsn(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:secret@db.example.com:5432/postgres",
    )
    assert get_postgres_dsn() == "postgresql://postgres:secret@db.example.com:5432/postgres"


def test_postgres_dsn_requires_url(monkeypatch):
    monkeypatch.setenv("DATABASE_DRIVER", "postgres")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_database_driver.cache_clear()
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_postgres_dsn()

"""
兼容入口：请使用 storage_bootstrap.bootstrap_storage。
"""
from src.infrastructure.persistence.storage_bootstrap import (  # noqa: F401
    bootstrap_sqlite_storage,
    bootstrap_storage,
)

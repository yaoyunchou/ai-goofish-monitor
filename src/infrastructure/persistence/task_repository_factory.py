"""
任务仓储工厂。
"""
from __future__ import annotations

from src.domain.repositories.task_repository import TaskRepository
from src.infrastructure.persistence.sqlite_task_repository import SqliteTaskRepository


def create_task_repository(
    db_path: str | None = None,
    *,
    legacy_config_file: str | None = "config.json",
) -> TaskRepository:
    return SqliteTaskRepository(
        db_path=db_path,
        legacy_config_file=legacy_config_file,
    )

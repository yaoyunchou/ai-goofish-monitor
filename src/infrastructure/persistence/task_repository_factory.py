"""任务仓储工厂。"""
from __future__ import annotations

from src.domain.repositories.task_repository import TaskRepository
from src.infrastructure.persistence.task_repository import DbTaskRepository


def create_task_repository(
    *,
    legacy_config_file: str | None = "config.json",
) -> TaskRepository:
    return DbTaskRepository(legacy_config_file=legacy_config_file)

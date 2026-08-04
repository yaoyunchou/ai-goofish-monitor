"""
任务仓储工厂。

说明：实现类仍名为 SqliteTaskRepository（历史命名），实际通过 db_connection()
按 .env 数据库配置连接远程库或本地文件，并非固定本地文件库。
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

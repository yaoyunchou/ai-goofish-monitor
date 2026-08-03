"""
基于 SQLite 的任务仓储实现。
"""
from __future__ import annotations

import asyncio
import json
from typing import List, Optional

from src.domain.models.task import Task
from src.domain.repositories.task_repository import TaskRepository
from src.infrastructure.persistence.db_connection import db_connection
from src.infrastructure.persistence.sql_dialect import as_sql_bool, parse_json_field, upsert_task_sql
from src.infrastructure.persistence.storage_bootstrap import bootstrap_storage


def _row_to_task(row) -> Task:
    payload = dict(row)
    payload["enabled"] = bool(payload["enabled"])
    payload["analyze_images"] = bool(payload["analyze_images"])
    payload["personal_only"] = bool(payload["personal_only"])
    payload["free_shipping"] = bool(payload["free_shipping"])
    payload["is_running"] = bool(payload["is_running"])
    payload["keyword_rules"] = parse_json_field(
        payload.pop("keyword_rules_json"),
        default=[],
    )
    return Task(**payload)


def find_task_by_name_sync(task_name: str) -> Task | None:
    bootstrap_storage()
    with db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE task_name = ? ORDER BY id ASC LIMIT 1",
            (task_name,),
        ).fetchone()
    return _row_to_task(row) if row else None


class SqliteTaskRepository(TaskRepository):
    """基于 SQLite 的任务仓储"""

    def __init__(
        self,
        db_path: str | None = None,
        legacy_config_file: str | None = "config.json",
    ):
        self.db_path = db_path
        self.legacy_config_file = legacy_config_file

    async def find_all(self) -> List[Task]:
        return await asyncio.to_thread(self._find_all_sync)

    async def find_by_id(self, task_id: int) -> Optional[Task]:
        return await asyncio.to_thread(self._find_by_id_sync, task_id)

    async def save(self, task: Task) -> Task:
        return await asyncio.to_thread(self._save_sync, task)

    async def delete(self, task_id: int) -> bool:
        return await asyncio.to_thread(self._delete_sync, task_id)

    def _find_all_sync(self) -> List[Task]:
        bootstrap_storage(
            self.db_path,
            legacy_config_file=self.legacy_config_file,
        )
        with db_connection(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY id ASC").fetchall()
        return [_row_to_task(row) for row in rows]

    def _find_by_id_sync(self, task_id: int) -> Optional[Task]:
        bootstrap_storage(
            self.db_path,
            legacy_config_file=self.legacy_config_file,
        )
        with db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_task(row) if row else None

    def _save_sync(self, task: Task) -> Task:
        bootstrap_storage(
            self.db_path,
            legacy_config_file=self.legacy_config_file,
        )
        with db_connection(self.db_path) as conn:
            task_id = task.id
            if task_id is None:
                task_id = self._next_task_id(conn)
            payload = self._task_values(task.model_copy(update={"id": task_id}))
            conn.execute(upsert_task_sql(), payload)
            conn.commit()
        return task.model_copy(update={"id": task_id})

    def _delete_sync(self, task_id: int) -> bool:
        bootstrap_storage(
            self.db_path,
            legacy_config_file=self.legacy_config_file,
        )
        with db_connection(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
        return cursor.rowcount > 0

    def _next_task_id(self, conn) -> int:
        row = conn.execute("SELECT COALESCE(MAX(id), -1) AS max_id FROM tasks").fetchone()
        return int(row["max_id"]) + 1

    def _task_values(self, task: Task) -> dict:
        values = task.model_dump()
        values["enabled"] = as_sql_bool(task.enabled)
        values["analyze_images"] = as_sql_bool(task.analyze_images)
        values["personal_only"] = as_sql_bool(task.personal_only)
        values["free_shipping"] = as_sql_bool(task.free_shipping)
        values["is_running"] = as_sql_bool(task.is_running)
        values["keyword_rules_json"] = json.dumps(task.keyword_rules or [], ensure_ascii=False)
        values.pop("keyword_rules", None)
        return values

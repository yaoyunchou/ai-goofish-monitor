"""测试用内存任务仓储（不依赖任何数据库）。"""
from __future__ import annotations

import asyncio
from typing import Dict, List, Optional

from src.domain.models.task import Task
from src.domain.repositories.task_repository import TaskRepository


class InMemoryTaskRepository(TaskRepository):
    def __init__(self) -> None:
        self._tasks: Dict[int, Task] = {}
        self._next_id = 0

    async def find_all(self) -> List[Task]:
        return await asyncio.to_thread(self._find_all_sync)

    async def find_by_id(self, task_id: int) -> Optional[Task]:
        return await asyncio.to_thread(self._find_by_id_sync, task_id)

    async def save(self, task: Task) -> Task:
        return await asyncio.to_thread(self._save_sync, task)

    async def delete(self, task_id: int) -> bool:
        return await asyncio.to_thread(self._delete_sync, task_id)

    def _find_all_sync(self) -> List[Task]:
        return sorted(self._tasks.values(), key=lambda t: t.id or 0)

    def _find_by_id_sync(self, task_id: int) -> Optional[Task]:
        return self._tasks.get(task_id)

    def _save_sync(self, task: Task) -> Task:
        task_id = task.id
        if task_id is None:
            task_id = self._next_id
            self._next_id += 1
        else:
            self._next_id = max(self._next_id, int(task_id) + 1)
        saved = task.model_copy(update={"id": task_id})
        self._tasks[int(task_id)] = saved
        return saved

    def _delete_sync(self, task_id: int) -> bool:
        return self._tasks.pop(task_id, None) is not None

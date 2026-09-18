import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# Add repository root to the path so package imports work consistently
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

# 测试不连接 Supabase：使用隔离的空 .env
_pytest_env = repo_root / "data" / ".pytest-env"
_pytest_env.parent.mkdir(parents=True, exist_ok=True)
_pytest_env.write_text("# pytest isolated env\n", encoding="utf-8")

from src.infrastructure.config.env_manager import env_manager

env_manager.env_file = _pytest_env

os.environ.pop("DATABASE_URL", None)

from src.api import dependencies as deps
from src.api.routes import tasks
from tests.fakes.memory_task_repository import InMemoryTaskRepository
from tests.fakes.sqlite_connection import SqliteConnectionFactory
from src.services.task_service import TaskService
from src.services.task_generation_service import TaskGenerationService


@pytest.fixture()
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture()
def offline_db(monkeypatch):
    """让存储层在无 PG 环境下用内存 SQLite 做真实的 SQL 往返。

    生产代码不改动：只在测试进程内把 `db_connection` 模块的 `db_connection`
    符号替换为替身工厂。被测代码通过
    `from ... import db_connection` 取到的是同一个模块对象属性，因此替换后
    所有存储调用点都会命中替身（`storage_bootstrap` 亦不例外）。

    每个测试独占一套内存库，避免跨用例串数据。
    """
    from src.infrastructure.persistence import db_connection as db_connection_module

    factory = SqliteConnectionFactory(name=f"testdb_{id(monkeypatch)}")
    try:
        monkeypatch.setattr(
            db_connection_module, "db_connection", factory, raising=True
        )
        # 已被其他模块静态导入的引用也一并替换，保证语义一致。
        for module in _MODULES_REEXPORTING_DB_CONNECTION:
            if hasattr(module, "db_connection"):
                monkeypatch.setattr(module, "db_connection", factory, raising=False)
        yield factory
    finally:
        factory.reset()


def _iter_reexporting_modules():
    import importlib
    import pkgutil

    import src as src_package

    for module_info in pkgutil.walk_packages(
        src_package.__path__, prefix="src."
    ):
        try:
            yield importlib.import_module(module_info.name)
        except Exception:  # pragma: no cover - 可选依赖缺失时跳过
            continue


_MODULES_REEXPORTING_DB_CONNECTION = [
    module
    for module in _iter_reexporting_modules()
    if getattr(module, "db_connection", None) is not None
]


@pytest.fixture()
def load_json_fixture(fixtures_dir):
    def _load(name: str):
        return json.loads((fixtures_dir / name).read_text(encoding="utf-8"))

    return _load


@pytest.fixture()
def sample_task_payload():
    return {
        "task_name": "Sony A7M4",
        "enabled": True,
        "keyword": "sony a7m4",
        "description": "Good condition body with accessories",
        "analyze_images": True,
        "max_pages": 2,
        "personal_only": True,
        "min_price": "8000",
        "max_price": "16000",
        "cron": "*/15 * * * *",
        "ai_prompt_base_file": "prompts/base_prompt.txt",
        "ai_prompt_criteria_file": "prompts/sony_a7m4_criteria.txt",
        "decision_mode": "ai",
        "keyword_rules": [],
    }


class FakeProcessService:
    def __init__(self):
        self.started = []
        self.stopped = []
        self.reindexed = []
        self._on_started = None
        self._on_stopped = None

    def set_lifecycle_hooks(self, *, on_started=None, on_stopped=None):
        self._on_started = on_started
        self._on_stopped = on_stopped

    async def start_task(self, task_id: int, task_name: str) -> bool:
        self.started.append((task_id, task_name))
        if self._on_started:
            await self._on_started(task_id)
        return True

    async def stop_task(self, task_id: int, *, quiet: bool = False):
        self.stopped.append(task_id)
        if self._on_stopped:
            await self._on_stopped(task_id)

    def is_seller_subscription_running(self) -> bool:
        return False

    async def start_seller_subscription_job(self) -> bool:
        return True

    def reindex_after_delete(self, deleted_task_id: int):
        self.reindexed.append(deleted_task_id)


class FakeSchedulerService:
    def __init__(self):
        self.reload_calls = 0
        self.next_run_times = {}

    async def reload_jobs(self, tasks):
        self.reload_calls += 1
        base = datetime(2026, 3, 19, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        self.next_run_times = {
            task.id: base + timedelta(minutes=(index + 1) * 15)
            for index, task in enumerate(tasks)
            if task.id is not None and task.enabled and task.cron
        }

    async def reload_seller_subscription_job(self, schedule):
        self.subscription_schedule = schedule

    def get_next_run_time(self, task_id: int):
        return self.next_run_times.get(task_id)

    def get_seller_subscription_next_run_time(self):
        return getattr(self, "subscription_next_run_time", None)


@pytest.fixture()
def api_context(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text("[]", encoding="utf-8")

    repository = InMemoryTaskRepository()
    task_service = TaskService(repository)
    process_service = FakeProcessService()
    scheduler_service = FakeSchedulerService()
    task_generation_service = TaskGenerationService()

    app = FastAPI()
    app.include_router(tasks.router)

    def override_get_task_service():
        return task_service

    def override_get_process_service():
        return process_service

    def override_get_scheduler_service():
        return scheduler_service

    def override_get_task_generation_service():
        return task_generation_service

    async def mark_started(task_id: int):
        await task_service.update_task_status(task_id, True)

    async def mark_stopped(task_id: int):
        task = await task_service.get_task(task_id)
        if task:
            await task_service.update_task_status(task_id, False)

    process_service.set_lifecycle_hooks(on_started=mark_started, on_stopped=mark_stopped)

    app.dependency_overrides[deps.get_task_service] = override_get_task_service
    app.dependency_overrides[deps.get_process_service] = override_get_process_service
    app.dependency_overrides[deps.get_scheduler_service] = override_get_scheduler_service
    app.dependency_overrides[deps.get_task_generation_service] = override_get_task_generation_service

    return {
        "app": app,
        "config_file": config_file,
        "db_path": None,
        "process_service": process_service,
        "scheduler_service": scheduler_service,
        "task_generation_service": task_generation_service,
    }


@pytest.fixture()
def api_client(api_context):
    return TestClient(api_context["app"])

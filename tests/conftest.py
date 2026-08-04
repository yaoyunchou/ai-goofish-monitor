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

# 测试需要一个 Postgres 测试库，通过 TEST_DATABASE_URL 指定（勿复用生产库，会被清空）。
# 通过 env_manager 注入到一个临时 .env 文件，使其优先于进程环境变量（含 Cursor Cloud Secrets）。
# 未配置 TEST_DATABASE_URL 时，依赖数据库的用例会自动跳过，纯单元测试照常运行。
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "").strip()

_pytest_env = repo_root / "data" / ".pytest-env"
_pytest_env.parent.mkdir(parents=True, exist_ok=True)
_pytest_lines = []
if TEST_DATABASE_URL:
    _pytest_lines.append(f"DATABASE_URL={TEST_DATABASE_URL}")
_pytest_env.write_text("\n".join(_pytest_lines) + "\n", encoding="utf-8")

from src.infrastructure.config.env_manager import env_manager

env_manager.env_file = _pytest_env

# 避免本机/云端进程环境中的 DATABASE_URL 串连真实库
os.environ.pop("DATABASE_URL", None)

from src.infrastructure.persistence.database_config import get_database_driver

from src.api import dependencies as deps
from src.api.routes import tasks
from src.infrastructure.persistence.task_repository import DbTaskRepository
from src.services.task_service import TaskService
from src.services.task_generation_service import TaskGenerationService


# 需要在每个用例前清空的业务表（含外键依赖顺序）
_TRUNCATE_TABLES = (
    "collected_items",
    "result_blacklist_rules",
    "price_snapshots",
    "result_items",
    "tasks",
    "app_metadata",
)


@pytest.fixture()
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


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

    async def stop_task(self, task_id: int):
        self.stopped.append(task_id)
        if self._on_stopped:
            await self._on_stopped(task_id)

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

    def get_next_run_time(self, task_id: int):
        return self.next_run_times.get(task_id)


@pytest.fixture()
def clean_db():
    """清空测试库业务表，为依赖数据库的用例提供干净环境。"""
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL 未配置；需要可清空的 Postgres 测试库")
    from src.infrastructure.persistence.db_connection import db_connection

    with db_connection() as conn:
        for table in _TRUNCATE_TABLES:
            conn.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
        conn.commit()


@pytest.fixture()
def api_context(tmp_path, clean_db):
    config_file = tmp_path / "config.json"
    config_file.write_text("[]", encoding="utf-8")

    repository = DbTaskRepository(legacy_config_file=None)
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
        "process_service": process_service,
        "scheduler_service": scheduler_service,
        "task_generation_service": task_generation_service,
    }


@pytest.fixture()
def api_client(api_context):
    return TestClient(api_context["app"])

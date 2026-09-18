"""日志 API 集成测试。"""
import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.api.routes import logs
from src.domain.models.task import TaskCreate
from tests.fakes.memory_task_repository import InMemoryTaskRepository
from src.services.task_service import TaskService
from src.utils import resolve_task_log_path


def _client(tmp_path, monkeypatch, task_service) -> TestClient:
    monkeypatch.chdir(tmp_path)
    app = FastAPI()
    app.include_router(logs.router)
    app.dependency_overrides[deps.get_task_service] = lambda: task_service
    return TestClient(app)


def test_logs_require_task_id(tmp_path, monkeypatch):
    repo = InMemoryTaskRepository()
    service = TaskService(repo)
    client = _client(tmp_path, monkeypatch, service)

    resp = client.get("/api/logs")
    assert resp.status_code == 200
    assert "请选择任务" in resp.json()["new_content"]


def test_logs_incremental_read_and_clear(tmp_path, monkeypatch):
    repo = InMemoryTaskRepository()
    service = TaskService(repo)
    task = asyncio.run(
        service.create_task(
            TaskCreate(
                task_name="日志测试",
                keyword="demo",
                description="demo",
                max_pages=1,
            )
        )
    )
    log_path = tmp_path / "logs" / f"demo_{task.id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("line-1\n", encoding="utf-8")
    monkeypatch.setattr(
        logs,
        "resolve_task_log_path",
        lambda task_id, task_name: str(log_path),
    )

    client = _client(tmp_path, monkeypatch, service)

    first = client.get("/api/logs", params={"task_id": task.id, "from_pos": 0})
    assert first.status_code == 200
    body = first.json()
    assert "line-1" in body["new_content"]
    pos = body["new_pos"]

    log_path.write_text("line-1\nline-2\n", encoding="utf-8")
    second = client.get("/api/logs", params={"task_id": task.id, "from_pos": pos})
    assert "line-2" in second.json()["new_content"]

    tail = client.get(
        "/api/logs/tail",
        params={"task_id": task.id, "limit_lines": 10},
    )
    assert tail.status_code == 200
    assert "line-2" in tail.json()["content"]

    cleared = client.delete("/api/logs", params={"task_id": task.id})
    assert cleared.status_code == 200
    assert log_path.read_text(encoding="utf-8") == ""


def test_logs_support_seller_subscription_job(tmp_path, monkeypatch):
    from src.domain.seller_subscription import (
        SELLER_SUBSCRIPTION_JOB_ID,
        SELLER_SUBSCRIPTION_TASK_NAME,
    )

    repo = InMemoryTaskRepository()
    service = TaskService(repo)
    log_path = tmp_path / "logs" / f"{SELLER_SUBSCRIPTION_TASK_NAME}_{SELLER_SUBSCRIPTION_JOB_ID}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("seller-subscription-line\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    client = _client(tmp_path, monkeypatch, service)
    resp = client.get(
        "/api/logs",
        params={"task_id": SELLER_SUBSCRIPTION_JOB_ID, "from_pos": 0},
    )
    assert resp.status_code == 200
    assert "seller-subscription-line" in resp.json()["new_content"]

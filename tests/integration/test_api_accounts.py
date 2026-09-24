"""账号 API 集成测试。"""
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import accounts
def _client(tmp_path, monkeypatch) -> TestClient:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr(accounts, "_state_dir", lambda: str(state_dir))
    app = FastAPI()
    app.include_router(accounts.router)
    return TestClient(app)


def test_accounts_crud_flow(tmp_path, monkeypatch, offline_db):
    client = _client(tmp_path, monkeypatch)
    payload = {"name": "test-acc", "content": json.dumps({"cookies": []})}

    create = client.post("/api/accounts", json=payload)
    assert create.status_code == 200
    assert create.json()["name"] == "test-acc"

    listing = client.get("/api/accounts")
    assert listing.status_code == 200
    assert any(item["name"] == "test-acc" for item in listing.json())

    detail = client.get("/api/accounts/test-acc")
    assert detail.status_code == 200
    assert "cookies" in detail.json()["content"]

    update = client.put(
        "/api/accounts/test-acc",
        json={"content": json.dumps({"cookies": [{"name": "a"}]})},
    )
    assert update.status_code == 200

    delete = client.delete("/api/accounts/test-acc")
    assert delete.status_code == 200
    assert client.get("/api/accounts/test-acc").status_code == 404


def test_accounts_reject_invalid_name_and_json(tmp_path, monkeypatch, offline_db):
    client = _client(tmp_path, monkeypatch)

    bad_name = client.post(
        "/api/accounts",
        json={"name": "bad name!", "content": "{}"},
    )
    assert bad_name.status_code == 400

    bad_json = client.post(
        "/api/accounts",
        json={"name": "ok-name", "content": "not-json"},
    )
    assert bad_json.status_code == 400

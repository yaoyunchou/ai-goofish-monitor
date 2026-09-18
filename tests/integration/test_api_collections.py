"""收录 API 集成测试（mock collection_service）。"""
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import collections


def _client(monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(collections.router)
    return TestClient(app)


def test_list_collections(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        "src.services.collection_service.list_collections",
        AsyncMock(return_value=[{"id": 1, "result_item_id": 9}]),
    )
    resp = client.get("/api/collections")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["id"] == 1


def test_lookup_collection(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        "src.services.collection_service.lookup_result_item_id",
        lambda filename, item_id: 42,
    )
    monkeypatch.setattr(
        "src.services.collection_service.list_collections",
        AsyncMock(return_value=[{"id": 7, "result_item_id": 42}]),
    )
    resp = client.get(
        "/api/collections/lookup",
        params={"result_filename": "demo.jsonl", "item_id": "item-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["collected"] is True
    assert resp.json()["collection_id"] == 7


def test_collect_and_delete_collection(monkeypatch):
    client = _client(monkeypatch)
    sample = {
        "id": 3,
        "result_item_id": 11,
        "sku_fetch_status": "pending",
        "skus": [],
    }
    monkeypatch.setattr(
        "src.services.collection_service.collect_result_item",
        AsyncMock(return_value=sample),
    )
    monkeypatch.setattr(
        "src.services.collection_service.delete_collection",
        AsyncMock(return_value=True),
    )

    collect = client.post("/api/collections", json={"result_item_id": 11})
    assert collect.status_code == 200
    assert collect.json()["collection"]["id"] == 3

    delete = client.delete("/api/collections/3")
    assert delete.status_code == 200
    assert "取消收录" in delete.json()["message"]

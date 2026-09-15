from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import shop_analytics


def test_shop_analytics_overview_returns_empty_payload_when_no_snapshots(monkeypatch):
    async def fake_list_latest_by_cycle(_cycle: str):
        return []

    monkeypatch.setattr(shop_analytics, "list_latest_by_cycle", fake_list_latest_by_cycle)

    app = FastAPI()
    app.include_router(shop_analytics.router)
    client = TestClient(app)

    response = client.get("/api/shop-analytics/overview?cycle=1d")

    assert response.status_code == 200
    body = response.json()
    assert body["has_data"] is False
    assert "店铺数据快照" in body["empty_message"]

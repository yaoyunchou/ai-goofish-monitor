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


def _sample_dashboard(period: str = "today"):
    return {
        "period": period,
        "timezone": "Asia/Shanghai",
        "today": "2026-09-17",
        "range_start": "2026-09-11",
        "range_end": "2026-09-17",
        "anchor_day": "2026-09-17",
        "has_data": True,
        "freshness": {
            "last_captured_at": "2026-09-17T17:38:17+08:00",
            "last_run_at": "2026-09-17T17:38:17+08:00",
        },
        "cards": {
            "enabled_shop_count": 2,
            "shops_with_data": 2,
            "item_count": 181,
            "want_sum": 8344,
            "view_sum": 65071,
            "item_count_scope": "anchor_day" if period == "today" else "range",
            "want_view_scope": "anchor_day" if period == "today" else "latest_day_in_range",
        },
        "trend": [
            {"date": f"2026-09-{day:02d}", "want": None, "view": None}
            for day in range(11, 16)
        ]
        + [
            {"date": "2026-09-16", "want": 100, "view": 2000},
            {"date": "2026-09-17", "want": 8344, "view": 65071},
        ],
        "shops": [
            {
                "seller_user_id": "a",
                "shop_name": "笑笑书馆",
                "item_count": 80,
                "want_sum": 8175,
                "view_sum": 63308,
                "enabled": True,
            }
        ],
        "hot_items": [],
    }


def test_shop_analytics_dashboard_returns_subscription_payload(monkeypatch):
    async def fake_dashboard(period: str = "today", today=None):
        return _sample_dashboard(period)

    monkeypatch.setattr(shop_analytics, "get_subscription_dashboard", fake_dashboard)

    app = FastAPI()
    app.include_router(shop_analytics.router)
    client = TestClient(app)

    response = client.get("/api/shop-analytics/dashboard?period=today")
    assert response.status_code == 200
    body = response.json()
    assert body["has_data"] is True
    assert body["cards"]["item_count"] == 181
    assert body["cards"]["want_sum"] == 8344
    assert body["trend"][0]["want"] is None
    assert len(body["trend"]) == 7


def test_shop_analytics_dashboard_rejects_invalid_period():
    app = FastAPI()
    app.include_router(shop_analytics.router)
    client = TestClient(app)

    response = client.get("/api/shop-analytics/dashboard?period=30d")
    assert response.status_code == 422


def test_shop_analytics_dashboard_rejects_legacy_cycle_period():
    app = FastAPI()
    app.include_router(shop_analytics.router)
    client = TestClient(app)

    response = client.get("/api/shop-analytics/dashboard?period=1d")
    assert response.status_code == 422


def test_shop_analytics_dashboard_defaults_to_today(monkeypatch):
    seen = {}

    async def fake_dashboard(period: str = "today", today=None):
        seen["period"] = period
        return _sample_dashboard(period)

    monkeypatch.setattr(shop_analytics, "get_subscription_dashboard", fake_dashboard)

    app = FastAPI()
    app.include_router(shop_analytics.router)
    client = TestClient(app)

    response = client.get("/api/shop-analytics/dashboard")
    assert response.status_code == 200
    assert seen["period"] == "today"
    body = response.json()
    assert "empty_message" not in body
    assert body["period"] == "today"


def test_shop_analytics_dashboard_period_7d(monkeypatch):
    async def fake_dashboard(period: str = "today", today=None):
        return _sample_dashboard(period)

    monkeypatch.setattr(shop_analytics, "get_subscription_dashboard", fake_dashboard)

    app = FastAPI()
    app.include_router(shop_analytics.router)
    client = TestClient(app)

    response = client.get("/api/shop-analytics/dashboard?period=7d")
    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "7d"
    assert body["cards"]["item_count_scope"] == "range"
    assert body["cards"]["want_view_scope"] == "latest_day_in_range"
    assert len(body["trend"]) == 7

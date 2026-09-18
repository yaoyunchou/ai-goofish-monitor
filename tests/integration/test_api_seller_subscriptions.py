import pytest
from fastapi.testclient import TestClient

from src.app import app


@pytest.fixture()
def subscription_api_client():
    return TestClient(app)


def test_seller_subscription_crud_and_schedule(subscription_api_client, offline_db):
    api_client = subscription_api_client
    list_res = api_client.get("/api/seller-subscriptions")
    assert list_res.status_code == 200
    body = list_res.json()
    assert "items" in body
    assert "schedule" in body
    assert body["schedule"]["cron"]

    create_res = api_client.post(
        "/api/seller-subscriptions",
        json={
            "seller_url": "https://www.goofish.com/personal?userId=2221197154547",
            "note": "测试卖家",
        },
    )
    assert create_res.status_code == 200
    created = create_res.json()["item"]
    subscription_id = created["id"]
    assert created["seller_user_id"] == "2221197154547"

    patch_res = api_client.patch(
        f"/api/seller-subscriptions/{subscription_id}",
        json={"enabled": False},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["item"]["enabled"] is False

    list_after_disable = api_client.get("/api/seller-subscriptions")
    assert list_after_disable.status_code == 200
    disabled_row = next(
        item for item in list_after_disable.json()["items"] if item["id"] == subscription_id
    )
    assert disabled_row["enabled"] is False

    patch_enable_res = api_client.patch(
        f"/api/seller-subscriptions/{subscription_id}",
        json={"enabled": True},
    )
    assert patch_enable_res.status_code == 200
    assert patch_enable_res.json()["item"]["enabled"] is True

    schedule_res = api_client.patch(
        "/api/seller-subscriptions/schedule",
        json={"cron": "0 9 * * *", "enabled": True, "run_headless": True},
    )
    assert schedule_res.status_code == 200
    schedule_body = schedule_res.json()["schedule"]
    assert schedule_body["cron"] == "0 9 * * *"
    assert schedule_body["run_headless"] is True
    assert schedule_body["run_headless_effective"] is True
    assert "next_run_at" in schedule_body
    assert schedule_body["next_run_at"]

    stats_res_after = api_client.get("/api/seller-subscriptions/stats")
    assert stats_res_after.status_code == 200
    stats_after = stats_res_after.json()
    persisted = stats_after["schedule"]
    assert persisted["run_headless"] is True
    assert persisted["run_headless_effective"] is True
    assert "next_run_at" in stats_after
    assert "next_run_at" in persisted
    assert stats_after["next_run_at"] == persisted["next_run_at"]
    assert persisted["next_run_at"]

    stats_res = api_client.get("/api/seller-subscriptions/stats")
    assert stats_res.status_code == 200
    assert stats_res.json()["seller_count"] >= 0
    assert "next_run_at" in stats_res.json()

    delete_res = api_client.delete(f"/api/seller-subscriptions/{subscription_id}")
    assert delete_res.status_code == 200


def test_stats_next_run_at_null_when_scheduler_has_no_job(monkeypatch):
    from fastapi import FastAPI
    from src.api.dependencies import get_process_service, get_scheduler_service
    from src.api.routes import seller_subscriptions

    class _FakeScheduler:
        def get_seller_subscription_next_run_time(self):
            return None

    class _FakeProcess:
        def is_seller_subscription_running(self):
            return False

    async def _empty_list():
        return []

    async def _empty_items(*_args, **_kwargs):
        return []

    async def _enabled_schedule():
        return {"enabled": True, "cron": "0 1 * * *", "is_running": False}

    async def _noop_running(_value):
        return None

    monkeypatch.setattr(seller_subscriptions, "list_subscriptions", _empty_list)
    monkeypatch.setattr(seller_subscriptions, "list_latest_item_metrics", _empty_items)
    monkeypatch.setattr(seller_subscriptions, "get_schedule", _enabled_schedule)
    monkeypatch.setattr(seller_subscriptions, "set_subscription_running", _noop_running)

    app = FastAPI()
    app.include_router(seller_subscriptions.router)
    app.dependency_overrides[get_process_service] = lambda: _FakeProcess()
    app.dependency_overrides[get_scheduler_service] = lambda: _FakeScheduler()
    client = TestClient(app)

    response = client.get("/api/seller-subscriptions/stats")
    assert response.status_code == 200
    body = response.json()
    assert "next_run_at" in body
    assert body["next_run_at"] is None
    assert body["schedule"]["enabled"] is True
    assert body["schedule"]["next_run_at"] is None

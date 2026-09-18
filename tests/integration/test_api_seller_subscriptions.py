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

    schedule_res = api_client.patch(
        "/api/seller-subscriptions/schedule",
        json={"cron": "0 9 * * *", "enabled": True},
    )
    assert schedule_res.status_code == 200
    assert schedule_res.json()["schedule"]["cron"] == "0 9 * * *"

    stats_res = api_client.get("/api/seller-subscriptions/stats")
    assert stats_res.status_code == 200
    assert stats_res.json()["seller_count"] >= 0

    delete_res = api_client.delete(f"/api/seller-subscriptions/{subscription_id}")
    assert delete_res.status_code == 200

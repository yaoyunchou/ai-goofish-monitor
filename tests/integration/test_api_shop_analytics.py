"""店铺数据罗盘 API 集成测试：验证返回 JSON 而非 HTML。"""

from fastapi.testclient import TestClient

from src.api.routes import shop_analytics
from src.app import app

client = TestClient(app)


def _assert_json_response(response, expected_status: int = 200):
    assert response.status_code == expected_status
    assert "application/json" in response.headers.get("content-type", "")
    assert not response.text.lstrip().startswith("<"), (
        f"接口返回了 HTML 而非 JSON，body 开头: {response.text[:80]!r}"
    )
    return response.json()


def test_overview_returns_json_when_no_snapshots(monkeypatch):
    async def fake_empty(_cycle: str, _account=None):
        return []

    monkeypatch.setattr(shop_analytics, "list_latest_by_cycle", fake_empty)

    body = _assert_json_response(client.get("/api/shop-analytics/overview?cycle=1d"))
    assert body["has_data"] is False
    assert body["cycle"] == "1d"
    assert "店铺数据快照" in body["empty_message"]


def test_overview_returns_json_with_metrics_when_snapshots_exist(monkeypatch):
    async def fake_rows(_cycle: str, _account=None):
        return [
            {
                "shop_name": "测试店铺",
                "snapshot_date": "2026-09-15",
                "captured_at": "2026-09-15T12:00:00",
                "api_name": "overview.summary",
                "metrics": {
                    "metrics": {
                        "showPv": {"value": 1234, "display": "1,234"},
                    }
                },
            }
        ]

    monkeypatch.setattr(shop_analytics, "list_latest_by_cycle", fake_rows)

    body = _assert_json_response(client.get("/api/shop-analytics/overview?cycle=7d"))
    assert body["has_data"] is True
    assert body["shop_name"] == "测试店铺"
    assert body["metrics"]["showPv"]["value"] == 1234


def test_distribution_and_trend_return_json_when_empty(monkeypatch):
    async def fake_empty(_cycle: str, _account=None):
        return []

    monkeypatch.setattr(shop_analytics, "list_latest_by_cycle", fake_empty)

    dist = _assert_json_response(
        client.get("/api/shop-analytics/distribution?cycle=1d&type=source")
    )
    assert dist["has_data"] is False
    assert dist["items"] == []

    trend = _assert_json_response(
        client.get("/api/shop-analytics/trend?metric=showPv&days=30&cycle=1d")
    )
    assert trend["has_data"] is False
    assert trend["points"] == []


def test_unknown_api_path_returns_json_404_not_html():
    body = _assert_json_response(client.get("/api/shop-analytics/not-exists"), 404)
    assert "detail" in body

    body = _assert_json_response(client.get("/api/this-route-does-not-exist"), 404)
    assert "API 路由未找到" in body["detail"]

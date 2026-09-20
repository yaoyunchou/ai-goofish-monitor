"""卖家订阅监控健康度 API：路由契约。

重点回归：`GET /items/health` 必须声明在 `GET /items/{item_id}/detail` 之前，
否则 "health" 会被当作 item_id 吞掉（FastAPI 按注册顺序匹配）。

注意：校验类断言走真实 app（含全局 HTTPException handler），
纯路由顺序断言走隔离 app，避免引入 DB 依赖。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.api.routes.seller_subscriptions as routes_module


def _client() -> TestClient:
    """隔离 app：只用于路由存在性/顺序，不需要 DB。"""
    app = FastAPI()
    app.include_router(routes_module.router)
    return TestClient(app, raise_server_exceptions=False)


def _real_client() -> TestClient:
    """真实 app：带全局 HTTPException handler，能正确返回 400。"""
    from src.app import app

    return TestClient(app, raise_server_exceptions=False)


def _routes_for(fragment: str) -> list[tuple[str, str]]:
    return [
        (sorted(route.methods)[0], route.path)
        for route in routes_module.router.routes
        if fragment in route.path
    ]


def test_health_route_registered_before_item_detail():
    """静态路径 /items/health 必须早于参数化 /items/{item_id}/detail 注册。"""
    paths_in_order = [path for _, path in _routes_for("items")]
    health_index = paths_in_order.index("/api/seller-subscriptions/items/health")
    detail_index = paths_in_order.index("/api/seller-subscriptions/items/{item_id}/detail")
    assert health_index < detail_index, (
        "GET /items/health 被 /items/{item_id}/detail 遮蔽了，"
        f"当前注册顺序：{paths_in_order}"
    )


def test_health_endpoint_reaches_its_own_handler():
    """/items/health 不应命中 detail handler（即使 DB 不可用也不能是 404-detail）。"""
    client = _client()
    response = client.get("/api/seller-subscriptions/items/health")
    # DB 不可用时会是 500；关键是它不能走进 detail 分支
    assert response.status_code != 404, "health 路由被遮蔽，返回了 404"


def test_health_run_endpoint_exists():
    client = _client()
    response = client.post("/api/seller-subscriptions/items/health/run", params={"notify": False})
    assert response.status_code != 404


def test_restore_endpoint_exists():
    """路由必须存在，且请求能进到它自己的 handler。

    注意：本地 .env 配了真实库时，unmute_item 会真的查库、查不到就返回 False，
    handler 抛 404 —— 这和「路由被遮蔽」的 404 无法区分。所以这里把 unmute_item
    打桩成成功，让断言只反映路由本身。
    """
    client = _client()
    with patch.object(routes_module, "unmute_item", new=AsyncMock(return_value=True)):
        response = client.post(
            "/api/seller-subscriptions/items/ITEM1/restore",
            params={"seller_user_id": "seller-1"},
        )
    assert response.status_code == 200


def test_health_rejects_bad_week_start_format():
    """格式错误应在进入 DB 之前就被 400 拒绝。"""
    client = _real_client()
    response = client.get(
        "/api/seller-subscriptions/items/health", params={"week_start": "not-a-date"}
    )
    assert response.status_code == 400
    assert "YYYY-MM-DD" in response.text


def test_health_run_rejects_bad_week_start_format():
    client = _real_client()
    response = client.post(
        "/api/seller-subscriptions/items/health/run", params={"week_start": "13/09/2026"}
    )
    assert response.status_code == 400


def test_expected_health_routes_present():
    methods_and_paths = set(_routes_for("items"))
    assert ("GET", "/api/seller-subscriptions/items/health") in methods_and_paths
    assert ("POST", "/api/seller-subscriptions/items/health/run") in methods_and_paths
    assert ("POST", "/api/seller-subscriptions/items/{item_id}/restore") in methods_and_paths

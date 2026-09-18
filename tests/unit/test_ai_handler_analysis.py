"""ai_handler.get_ai_analysis 的测试。

注意：AI 兼容性降级逻辑（结构化输出/temperature/API 回退）已下移到
``src.infrastructure.external.ai_client.AIClient._call_ai``，其测试见
``tests/unit/test_ai_client.py``。本文件只覆盖 ``get_ai_analysis`` 自身的职责：

- 客户端不可用 / prompt 缺失时提前返回 None
- 响应解析与格式校验成功时返回解析结果
- 空响应 / 解析失败时按 4 次上限重试后抛错
- 模型返回多个 JSON 对象时取第一个
"""

import asyncio

import pytest

import src.ai_handler as ai_handler


class _FakeSettings:
    """最小化的 AISettings 替身，仅暴露 get_ai_analysis 读取的属性。"""

    enable_response_format = True

    def normalized_provider(self) -> str:
        return "openai"


class _FakeAIClient:
    """记录 `_call_ai` 调用参数的 AIClient 替身。"""

    def __init__(self, call_impl, available: bool = True):
        self.settings = _FakeSettings()
        self._call_impl = call_impl
        self._available = available
        self.calls: list[dict] = []

    def is_available(self) -> bool:
        return self._available

    async def _call_ai(self, messages, **kwargs):
        self.calls.append(kwargs)
        return await self._call_impl(**kwargs)


VALID_PAYLOAD = (
    '{"prompt_version":"v1","is_recommended":true,'
    '"reason":"ok","risk_tags":[],"criteria_analysis":{"seller_type":"个人"}}'
)


def _install_fake_client(monkeypatch, call_impl, available: bool = True) -> _FakeAIClient:
    """把 ai_handler 的 AIClient 单例替换为替身，并固定模型名与输出格式开关。"""
    fake = _FakeAIClient(call_impl, available=available)
    monkeypatch.setattr(ai_handler, "_ai_client_singleton", fake)
    monkeypatch.setattr(ai_handler, "MODEL_NAME", "fake-model")
    monkeypatch.setattr(ai_handler, "ENABLE_RESPONSE_FORMAT", True)
    return fake


def test_get_ai_analysis_returns_none_when_client_unavailable(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    async def fake_call(**_kwargs):
        raise AssertionError("客户端不可用时不应发起调用")

    _install_fake_client(monkeypatch, fake_call, available=False)

    result = asyncio.run(
        ai_handler.get_ai_analysis(
            {"商品信息": {"商品ID": "0", "商品标题": "测试商品"}},
            image_paths=[],
            prompt_text="请输出 JSON",
        )
    )

    assert result is None


def test_get_ai_analysis_returns_none_when_prompt_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    async def fake_call(**_kwargs):
        raise AssertionError("缺少 prompt 时不应发起调用")

    _install_fake_client(monkeypatch, fake_call)

    result = asyncio.run(
        ai_handler.get_ai_analysis(
            {"商品信息": {"商品ID": "0", "商品标题": "测试商品"}},
            image_paths=[],
            prompt_text="",
        )
    )

    assert result is None


def test_get_ai_analysis_returns_parsed_json(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    call_count = {"value": 0}

    async def fake_call(**_kwargs):
        call_count["value"] += 1
        return VALID_PAYLOAD

    fake = _install_fake_client(monkeypatch, fake_call)

    result = asyncio.run(
        ai_handler.get_ai_analysis(
            {"商品信息": {"商品ID": "2", "商品标题": "测试商品2"}},
            image_paths=[],
            prompt_text="请输出 JSON",
        )
    )

    assert result["is_recommended"] is True
    assert call_count["value"] == 1
    assert len(fake.calls) == 1
    assert fake.calls[0]["temperature"] == 0.1
    assert fake.calls[0]["enable_json_output"] is True


def test_get_ai_analysis_stops_after_internal_retries_when_content_is_none(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    call_count = {"value": 0}

    async def fake_call(**_kwargs):
        call_count["value"] += 1
        return ""

    _install_fake_client(monkeypatch, fake_call)

    with pytest.raises(Exception):
        asyncio.run(
            ai_handler.get_ai_analysis(
                {"商品信息": {"商品ID": "1", "商品标题": "测试商品"}},
                image_paths=[],
                prompt_text="请输出 JSON",
            )
        )

    assert call_count["value"] == 4


def test_get_ai_analysis_retries_when_response_is_not_valid_json(monkeypatch, tmp_path):
    """非法 JSON 应按 4 次上限重试后抛 ValueError。"""
    monkeypatch.chdir(tmp_path)
    call_count = {"value": 0}

    async def fake_call(**_kwargs):
        call_count["value"] += 1
        return "这不是 JSON"

    _install_fake_client(monkeypatch, fake_call)

    with pytest.raises(Exception):
        asyncio.run(
            ai_handler.get_ai_analysis(
                {"商品信息": {"商品ID": "6", "商品标题": "测试商品6"}},
                image_paths=[],
                prompt_text="请输出 JSON",
            )
        )

    assert call_count["value"] == 4


def test_get_ai_analysis_recovers_when_later_attempt_returns_valid_json(
    monkeypatch, tmp_path
):
    """前一次返回非法 JSON、后一次合法时，应重试并成功返回。"""
    monkeypatch.chdir(tmp_path)
    state = {"count": 0}

    async def fake_call(**_kwargs):
        state["count"] += 1
        if state["count"] == 1:
            return "这不是 JSON"
        return VALID_PAYLOAD

    fake = _install_fake_client(monkeypatch, fake_call)

    result = asyncio.run(
        ai_handler.get_ai_analysis(
            {"商品信息": {"商品ID": "7", "商品标题": "测试商品7"}},
            image_paths=[],
            prompt_text="请输出 JSON",
        )
    )

    assert result["reason"] == "ok"
    assert state["count"] == 2
    assert len(fake.calls) == 2
    assert fake.calls[0]["temperature"] == 0.1
    assert fake.calls[1]["temperature"] == 0.05


def test_get_ai_analysis_uses_first_json_object_when_model_returns_multiple_objects(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)

    async def fake_call(**_kwargs):
        return """```json
{"prompt_version":"v1","is_recommended":true,"reason":"first","risk_tags":[],"criteria_analysis":{"seller_type":"个人"}}
{"prompt_version":"v1","is_recommended":false,"reason":"second","risk_tags":[],"criteria_analysis":{"seller_type":"商家"}}
```"""

    _install_fake_client(monkeypatch, fake_call)

    result = asyncio.run(
        ai_handler.get_ai_analysis(
            {"商品信息": {"商品ID": "5", "商品标题": "测试商品5"}},
            image_paths=[],
            prompt_text="请输出 JSON",
        )
    )

    assert result["is_recommended"] is True
    assert result["reason"] == "first"

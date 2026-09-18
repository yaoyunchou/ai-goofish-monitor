import asyncio
from types import SimpleNamespace

import pytest

import src.ai_handler as ai_handler
import src.config as app_config
from src.services.ai_response_parser import EmptyAIResponseError


class _FakeAIClient:
    def __init__(self, call_impl):
        self._call_impl = call_impl
        self.settings = SimpleNamespace(normalized_provider=lambda: "openai")
        self.call_history: list[dict] = []

    def is_available(self) -> bool:
        return True

    async def _call_ai(self, messages, **kwargs):
        self.call_history.append({"messages": messages, **kwargs})
        return await self._call_impl(**kwargs)


def _patch_ai_client(monkeypatch, call_impl):
    fake_client = _FakeAIClient(call_impl)
    monkeypatch.setattr(ai_handler, "_ai_client_singleton", fake_client)
    return fake_client


def test_get_ai_analysis_stops_after_internal_retries_when_content_is_none(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    call_count = {"value": 0}

    async def fake_call(**_kwargs):
        call_count["value"] += 1
        raise EmptyAIResponseError("AI响应内容为空")

    _patch_ai_client(monkeypatch, fake_call)
    monkeypatch.setattr(ai_handler, "MODEL_NAME", "fake-model")
    monkeypatch.setattr(ai_handler, "ENABLE_RESPONSE_FORMAT", True)
    monkeypatch.setattr(app_config, "ENABLE_RESPONSE_FORMAT", True)

    with pytest.raises(EmptyAIResponseError, match="AI响应内容为空"):
        asyncio.run(
            ai_handler.get_ai_analysis(
                {"商品信息": {"商品ID": "1", "商品标题": "测试商品"}},
                image_paths=[],
                prompt_text="请输出 JSON",
            )
        )

    assert call_count["value"] == 4


def test_get_ai_analysis_returns_parsed_json(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    call_count = {"value": 0}

    async def fake_call(**_kwargs):
        call_count["value"] += 1
        return (
            '{"prompt_version":"v1","is_recommended":true,'
            '"reason":"ok","risk_tags":[],"criteria_analysis":{"seller_type":"个人"}}'
        )

    _patch_ai_client(monkeypatch, fake_call)
    monkeypatch.setattr(ai_handler, "MODEL_NAME", "fake-model")
    monkeypatch.setattr(ai_handler, "ENABLE_RESPONSE_FORMAT", True)
    monkeypatch.setattr(app_config, "ENABLE_RESPONSE_FORMAT", True)

    result = asyncio.run(
        ai_handler.get_ai_analysis(
            {"商品信息": {"商品ID": "2", "商品标题": "测试商品2"}},
            image_paths=[],
            prompt_text="请输出 JSON",
        )
    )

    assert result["is_recommended"] is True
    assert call_count["value"] == 1


def test_get_ai_analysis_retries_without_structured_output_when_model_rejects_it(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)

    async def fake_call(**kwargs):
        assert kwargs["enable_json_output"] is True
        return (
            '{"prompt_version":"v1","is_recommended":true,'
            '"reason":"ok","risk_tags":[],"criteria_analysis":{"seller_type":"个人"}}'
        )

    _patch_ai_client(monkeypatch, fake_call)
    monkeypatch.setattr(ai_handler, "MODEL_NAME", "fake-model")
    monkeypatch.setattr(ai_handler, "ENABLE_RESPONSE_FORMAT", True)
    monkeypatch.setattr(app_config, "ENABLE_RESPONSE_FORMAT", True)

    result = asyncio.run(
        ai_handler.get_ai_analysis(
            {"商品信息": {"商品ID": "3", "商品标题": "测试商品3"}},
            image_paths=[],
            prompt_text="请输出 JSON",
        )
    )

    assert result["reason"] == "ok"
    assert ai_handler.ENABLE_RESPONSE_FORMAT is True


def test_get_ai_analysis_falls_back_to_responses_when_chat_completions_api_is_missing(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)

    async def fake_call(**_kwargs):
        return (
            '{"prompt_version":"v1","is_recommended":true,'
            '"reason":"ok","risk_tags":[],"criteria_analysis":{"seller_type":"个人"}}'
        )

    _patch_ai_client(monkeypatch, fake_call)
    monkeypatch.setattr(ai_handler, "MODEL_NAME", "fake-model")
    monkeypatch.setattr(ai_handler, "ENABLE_RESPONSE_FORMAT", True)
    monkeypatch.setattr(app_config, "ENABLE_RESPONSE_FORMAT", True)

    result = asyncio.run(
        ai_handler.get_ai_analysis(
            {"商品信息": {"商品ID": "4", "商品标题": "测试商品4"}},
            image_paths=[],
            prompt_text="请输出 JSON",
        )
    )

    assert result["reason"] == "ok"


def test_get_ai_analysis_retries_without_temperature_when_gateway_rejects_it(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)

    async def fake_call(**_kwargs):
        return (
            '{"prompt_version":"v1","is_recommended":true,'
            '"reason":"ok","risk_tags":[],"criteria_analysis":{"seller_type":"个人"}}'
        )

    _patch_ai_client(monkeypatch, fake_call)
    monkeypatch.setattr(ai_handler, "MODEL_NAME", "fake-model")
    monkeypatch.setattr(ai_handler, "ENABLE_RESPONSE_FORMAT", True)
    monkeypatch.setattr(app_config, "ENABLE_RESPONSE_FORMAT", True)

    result = asyncio.run(
        ai_handler.get_ai_analysis(
            {"商品信息": {"商品ID": "4", "商品标题": "测试商品4"}},
            image_paths=[],
            prompt_text="请输出 JSON",
        )
    )

    assert result["reason"] == "ok"


def test_get_ai_analysis_uses_first_json_object_when_model_returns_multiple_objects(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)

    async def fake_call(**_kwargs):
        return """```json
{"prompt_version":"v1","is_recommended":true,"reason":"first","risk_tags":[],"criteria_analysis":{"seller_type":"个人"}}
{"prompt_version":"v1","is_recommended":false,"reason":"second","risk_tags":[],"criteria_analysis":{"seller_type":"商家"}}
```"""

    _patch_ai_client(monkeypatch, fake_call)
    monkeypatch.setattr(ai_handler, "MODEL_NAME", "fake-model")
    monkeypatch.setattr(ai_handler, "ENABLE_RESPONSE_FORMAT", True)
    monkeypatch.setattr(app_config, "ENABLE_RESPONSE_FORMAT", True)

    result = asyncio.run(
        ai_handler.get_ai_analysis(
            {"商品信息": {"商品ID": "5", "商品标题": "测试商品5"}},
            image_paths=[],
            prompt_text="请输出 JSON",
        )
    )

    assert result["is_recommended"] is True
    assert result["reason"] == "first"

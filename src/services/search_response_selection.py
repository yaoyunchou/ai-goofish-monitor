"""
选择用于解析的搜索 API 响应（避免空 resultList / 筛选覆盖有效首屏数据）。
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.search_response_utils import extract_search_result_list, summarize_search_payload
from src.services.search_pagination import is_search_results_response
from src.utils import log_time


async def _response_payload(response: Any) -> Optional[dict]:
    if response is None or not getattr(response, "ok", False):
        return None
    try:
        return await response.json()
    except Exception as exc:
        log_time(f"搜索响应 JSON 解析失败: {type(exc).__name__}: {exc}")
        return None


async def result_list_length(response: Any) -> int:
    payload = await _response_payload(response)
    if payload is None:
        return -1
    return len(extract_search_result_list(payload))


async def choose_search_response_for_parse(
    page: Any,
    initial_response: Any,
    final_response: Any,
) -> Any:
    """
    在 initial（首屏搜索）与 final（筛选后）之间选用 resultList 非空的响应；
    若均为空则滚动触发一次新的搜索请求。
    """
    candidates: list[tuple[str, Any, int]] = []
    for label, resp in (("initial", initial_response), ("final", final_response)):
        if resp is None:
            continue
        length = await result_list_length(resp)
        candidates.append((label, resp, length))
        log_time(
            f"[搜索诊断] 候选响应 {label}: ok={getattr(resp, 'ok', False)}, "
            f"resultList_len={length}, url={str(getattr(resp, 'url', ''))[:96]}"
        )

    viable = [c for c in candidates if c[2] > 0]
    if viable:
        viable.sort(key=lambda x: x[2], reverse=True)
        label, resp, length = viable[0]
        log_time(f"选用搜索响应: {label}（resultList_len={length}）")
        return resp

    log_time("首屏/筛选搜索响应均无 resultList，尝试滚动触发后续搜索 API…")
    try:
        async with page.expect_response(
            is_search_results_response,
            timeout=12_000,
        ) as response_info:
            await page.evaluate("window.scrollBy(0, Math.min(600, document.body.scrollHeight))")
            await asyncio.sleep(1.5)
        retry_resp = await response_info.value
        retry_len = await result_list_length(retry_resp)
        log_time(
            f"[搜索诊断] 滚动重试: ok={retry_resp.ok}, resultList_len={retry_len}, "
            f"url={str(retry_resp.url)[:96]}"
        )
        if retry_len > 0:
            return retry_resp
    except PlaywrightTimeoutError:
        log_time("滚动后 12s 内未捕获到新的搜索 API 响应。")

    for label, resp, _ in candidates:
        payload = await _response_payload(resp)
        if payload is not None:
            print(f"LOG: [搜索诊断/{label}] {summarize_search_payload(payload)}")

    if final_response is not None and getattr(final_response, "ok", False):
        return final_response
    return initial_response

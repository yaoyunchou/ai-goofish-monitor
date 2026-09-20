"""
商品详情 SKU：优先 MTOP HTTP（与详情页 curl 一致），失败时 Playwright 兜底。
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright
import requests

from src.config import DETAIL_API_URL_PATTERN, RUN_HEADLESS
from src.item_detail_parser import (
    extract_skus_from_detail_payloads,
    parse_title_sku_fragments,
)
from src.scraper import _default_context_options, _resolve_browser_channel
from src.services.idle_mtop_client import (
    IdleMtopError,
    extract_item_id_from_link,
    fetch_idle_pc_detail,
    resolve_state_file as resolve_mtop_state_file,
)
from src.utils import log_time

SKU_API_FRAGMENTS = (
    DETAIL_API_URL_PATTERN,
    "mtop.taobao.idle",
    "sku",
    "skuprice",
    "idle.pc.detail",
    "idle.item",
)


def _resolve_state_file() -> str:
    return resolve_mtop_state_file(None)


def _build_sku_result(
    *,
    skus: List[dict],
    captured: List[dict],
    title: str,
    fetch_method: str,
    item_id: Optional[str] = None,
    detail_data: Optional[dict] = None,
) -> Dict[str, Any]:
    title_fragments = parse_title_sku_fragments(title)
    if not skus and title_fragments:
        skus = [
            {
                "sku_id": "",
                "label": " / ".join(f"{f['name']}: {f['value']}" for f in title_fragments),
                "price": None,
                "price_display": "",
                "properties": title_fragments,
                "in_stock": True,
                "source": "title_parse",
            }
        ]
    payload: Dict[str, Any] = {
        "skus": skus,
        "raw_payload_count": len(captured),
        "title_fragments": title_fragments,
        "fetched_at": datetime.now().isoformat(),
        "fetch_method": fetch_method,
    }
    if item_id:
        payload["item_id"] = item_id
    if detail_data is not None:
        payload["detail_data"] = detail_data
    return payload


async def fetch_idle_pc_detail_payload(
    link: str,
    *,
    item_id: Optional[str] = None,
    state_file: Optional[str] = None,
) -> dict:
    """直接调用 mtop.taobao.idle.pc.detail（需 state 内有效 Cookie / _m_h5_tk）。"""
    resolved_id = (item_id or extract_item_id_from_link(link) or "").strip()
    if not resolved_id:
        raise ValueError("无法从链接解析 itemId，请传入 item_id。")
    storage = state_file or _resolve_state_file()
    return await asyncio.to_thread(
        fetch_idle_pc_detail,
        resolved_id,
        state_file=storage,
    )


async def _fetch_skus_via_mtop(
    link: str,
    *,
    title: str,
    state_file: Optional[str],
) -> Dict[str, Any]:
    storage = state_file or _resolve_state_file()
    item_id = extract_item_id_from_link(link)
    if not item_id:
        raise IdleMtopError("链接中无 itemId")
    log_time(f"[SKU] MTOP 路径开始 itemId={item_id} link={link}")
    detail_json = await asyncio.to_thread(
        fetch_idle_pc_detail,
        item_id,
        state_file=storage,
    )
    captured = [detail_json]
    detail_data = detail_json.get("data") if isinstance(detail_json.get("data"), dict) else {}
    item_do = detail_data.get("itemDO") or {}
    log_time(
        f"[SKU] MTOP 成功 title={item_do.get('title', '?')[:30]} "
        f"soldPrice={item_do.get('soldPrice')} skuList={len(item_do.get('skuList') or [])}条"
    )
    skus = await extract_skus_from_detail_payloads(captured, fallback_title=title)
    log_time(f"[SKU] 解析出 {len(skus)} 个 SKU")
    return _build_sku_result(
        skus=skus,
        captured=captured,
        title=title,
        fetch_method="mtop",
        item_id=item_id,
        detail_data=detail_data,
    )


async def fetch_item_skus(
    link: str,
    *,
    title: str = "",
    state_file: Optional[str] = None,
    wait_seconds: float = 2.5,
) -> Dict[str, Any]:
    """
    返回 { skus, raw_payload_count, title_fragments, fetched_at, fetch_method, detail_data? }
    """
    log_time(f"[SKU] 开始拉取 link={link} title={title[:30] if title else '?'}")
    try:
        return await _fetch_skus_via_mtop(link, title=title, state_file=state_file)
    except (IdleMtopError, FileNotFoundError, ValueError, requests.RequestException, OSError) as exc:
        log_time(f"[SKU] MTOP 路径失败，切换 Playwright 兜底: {type(exc).__name__}: {exc}")

    storage = state_file or _resolve_state_file()
    from src.services.account_state_store import get_account_state
    state_data = get_account_state(storage)
    if state_data is None:
        raise FileNotFoundError(f"登录状态不存在: {storage}")
    if not isinstance(state_data, dict):
        raise ValueError("登录状态格式无效")

    log_time(f"[SKU] Playwright 兜底启动 account={storage}")
    captured: List[dict] = []

    async def on_response(response):
        url = response.url or ""
        if not any(fragment in url for fragment in SKU_API_FRAGMENTS):
            return
        if response.request.method not in {"GET", "POST"}:
            return
        try:
            if not response.ok:
                return
            payload = await response.json()
            if isinstance(payload, dict):
                captured.append(payload)
                log_time(f"[SKU] Playwright 捕获接口 ({len(captured)}): {url[:80]}")
        except Exception:
            return

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=RUN_HEADLESS,
            channel=_resolve_browser_channel(),
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            storage_state=state_data,
            **_default_context_options(),
        )
        page = await context.new_page()
        page.on("response", on_response)
        try:
            await page.goto(link, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(wait_seconds)
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
        finally:
            page.remove_listener("response", on_response)
            await context.close()
            await browser.close()

    skus = await extract_skus_from_detail_payloads(captured, fallback_title=title)
    log_time(f"[SKU] Playwright 完成 捕获{len(captured)}条 解析{len(skus)}个SKU")

    # 从捕获的响应中提取完整 detail_data（itemDO + sellerDO）
    detail_data: Optional[dict] = None
    for payload in captured:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if isinstance(data, dict) and (data.get("itemDO") or data.get("sellerDO")):
            detail_data = data
            break

    item_id = extract_item_id_from_link(link)
    return _build_sku_result(
        skus=skus,
        captured=captured,
        title=title,
        fetch_method="playwright",
        item_id=item_id,
        detail_data=detail_data,
    )

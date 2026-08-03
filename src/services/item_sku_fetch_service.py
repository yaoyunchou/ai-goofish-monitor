"""
使用 Playwright 打开商品详情并捕获 SKU / 价格接口。
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright

from src.config import DETAIL_API_URL_PATTERN, RUN_HEADLESS, STATE_FILE
from src.item_detail_parser import (
    extract_skus_from_detail_payloads,
    parse_title_sku_fragments,
)
from src.scraper import _default_context_options, _resolve_browser_channel

SKU_API_FRAGMENTS = (
    DETAIL_API_URL_PATTERN,
    "mtop.taobao.idle",
    "sku",
    "skuprice",
    "idle.pc.detail",
    "idle.item",
)


def _resolve_state_file() -> str:
    if os.path.exists(STATE_FILE):
        return STATE_FILE
    state_dir = os.path.join("state")
    if os.path.isdir(state_dir):
        for name in sorted(os.listdir(state_dir)):
            if name.endswith(".json"):
                return os.path.join(state_dir, name)
    raise FileNotFoundError("未找到闲鱼登录状态文件，请先在账号页导入 state。")


async def fetch_item_skus(
    link: str,
    *,
    title: str = "",
    state_file: Optional[str] = None,
    wait_seconds: float = 2.5,
) -> Dict[str, Any]:
    """
    返回 { skus: [...], raw_payload_count, title_fragments, fetched_at }
    """
    storage = state_file or _resolve_state_file()
    if not os.path.exists(storage):
        raise FileNotFoundError(f"登录状态文件不存在: {storage}")

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
        except Exception:
            return

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=RUN_HEADLESS,
            channel=_resolve_browser_channel(),
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            storage_state=storage,
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

    from datetime import datetime

    return {
        "skus": skus,
        "raw_payload_count": len(captured),
        "title_fragments": title_fragments,
        "fetched_at": datetime.now().isoformat(),
    }

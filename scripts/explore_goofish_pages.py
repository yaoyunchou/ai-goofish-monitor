"""探索闲鱼用户主页与卖家工作台页面，输出结构与 API 快照。"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import Response, async_playwright

from src.scraper import (
    _build_context_overrides,
    _build_extra_headers,
    _clean_kwargs,
    _default_context_options,
    _resolve_browser_channel,
)

STATE_FILE = ROOT / "docs" / "exploration" / "temp_login_state.json"
OUTPUT_DIR = ROOT / "docs" / "exploration" / "snapshots"

PERSONAL_URL = (
    "https://www.goofish.com/personal?"
    "spm=a21ybx.item.itemHeader.1.6e9e3da6wDtisc&userId=2221197154547"
)
SELLER_URL = "https://seller.goofish.com/?site=COMMONPRO#/seller-data/data"

API_KEYWORDS = (
    "mtop.",
    "h5api",
    "goofish.com",
    "taobao.com",
    "alicdn.com",
)


def _load_snapshot(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _is_interesting_api(url: str) -> bool:
    lowered = url.lower()
    if not any(keyword in lowered for keyword in API_KEYWORDS):
        return False
    if any(ext in lowered for ext in (".js", ".css", ".png", ".jpg", ".webp", ".woff", ".svg")):
        return False
    return True


def _extract_api_name(url: str) -> str:
    match = re.search(r"/h5/([^/?]+)", url)
    if match:
        return match.group(1)
    path = urlparse(url).path.rstrip("/").split("/")[-1]
    return path or url


async def _collect_dom_summary(page) -> dict[str, Any]:
    return await page.evaluate(
        """() => {
            const text = (el) => (el && el.textContent ? el.textContent.trim() : '');
            const pickTexts = (selector, limit = 20) =>
                Array.from(document.querySelectorAll(selector))
                    .slice(0, limit)
                    .map((el) => text(el))
                    .filter(Boolean);

            const headings = pickTexts('h1, h2, h3, [role="heading"]', 30);
            const navItems = pickTexts('nav a, [class*="menu"] a, [class*="Menu"] li, [class*="tab"]', 40);
            const buttons = pickTexts('button, [role="button"]', 40);
            const links = Array.from(document.querySelectorAll('a[href]'))
                .slice(0, 60)
                .map((a) => ({ text: text(a), href: a.getAttribute('href') }))
                .filter((item) => item.text || item.href);

            const title = document.title;
            const metaDesc = document.querySelector('meta[name="description"]')?.content || '';
            const hash = location.hash;
            const bodyPreview = (document.body?.innerText || '')
                .replace(/\\s+/g, ' ')
                .trim()
                .slice(0, 4000);

            return {
                title,
                metaDesc,
                hash,
                url: location.href,
                headings,
                navItems,
                buttons,
                links,
                bodyPreview,
            };
        }"""
    )


async def _explore_page(
    context,
    *,
    name: str,
    url: str,
    wait_ms: int = 8000,
    extra_actions: list | None = None,
) -> dict[str, Any]:
    page = await context.new_page()
    apis: list[dict[str, Any]] = []
    api_samples: dict[str, Any] = {}

    async def on_response(response: Response) -> None:
        req_url = response.url
        if not _is_interesting_api(req_url):
            return
        entry = {
            "url": req_url,
            "status": response.status,
            "method": response.request.method,
            "api": _extract_api_name(req_url),
        }
        apis.append(entry)
        api_name = entry["api"]
        if api_name in api_samples:
            return
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type.lower():
            return
        try:
            payload = await response.json()
            api_samples[api_name] = payload
        except Exception:
            pass

    page.on("response", on_response)

    result: dict[str, Any] = {
        "name": name,
        "requestedUrl": url,
        "exploredAt": datetime.now(timezone.utc).isoformat(),
    }

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(wait_ms)
        if extra_actions:
            for action in extra_actions:
                await action(page)
                await page.wait_for_timeout(2500)
        result["finalUrl"] = page.url
        result["dom"] = await _collect_dom_summary(page)
        screenshot_path = OUTPUT_DIR / f"{name}.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        result["screenshot"] = str(screenshot_path.relative_to(ROOT)).replace("\\", "/")
    except Exception as exc:
        result["error"] = str(exc)
        result["finalUrl"] = page.url
    finally:
        page.remove_listener("response", on_response)
        await page.close()

    deduped: dict[str, dict[str, Any]] = {}
    for item in apis:
        deduped[item["api"]] = item
    result["apis"] = sorted(deduped.values(), key=lambda x: x["api"])
    result["apiSamples"] = api_samples
    return result


async def _scroll_page(page) -> None:
    for _ in range(4):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1200)


async def _click_rating_tab(page) -> None:
    locator = page.locator("//div[text()='信用及评价']/ancestor::li")
    if await locator.count() > 0:
        await locator.first.click()


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    context_kwargs = _default_context_options()
    storage_state = None
    if STATE_FILE.exists() and STATE_FILE.stat().st_size > 0:
        snapshot = _load_snapshot(STATE_FILE)
        storage_state = {"cookies": snapshot.get("cookies", [])}
        context_kwargs.update(_build_context_overrides(snapshot))
        extra_headers = _build_extra_headers(snapshot.get("headers"))
        if extra_headers:
            context_kwargs["extra_http_headers"] = extra_headers
        context_kwargs = _clean_kwargs(context_kwargs)
    else:
        print(f"警告: 未找到有效登录态 {STATE_FILE}，将以匿名/未登录方式探索页面。")

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=launch_args,
            channel=_resolve_browser_channel(),
        )
        if storage_state:
            context = await browser.new_context(storage_state=storage_state, **context_kwargs)
        else:
            context = await browser.new_context(**context_kwargs)

        personal = await _explore_page(
            context,
            name="personal_profile",
            url=PERSONAL_URL,
            wait_ms=6000,
            extra_actions=[_scroll_page, _click_rating_tab, _scroll_page],
        )
        seller = await _explore_page(
            context,
            name="seller_workbench",
            url=SELLER_URL,
            wait_ms=10000,
            extra_actions=[_scroll_page],
        )

        await browser.close()

    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "stateFile": str(STATE_FILE.relative_to(ROOT)).replace("\\", "/"),
        "pages": [personal, seller],
    }

    json_path = OUTPUT_DIR / "exploration_snapshot.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "output": str(json_path.relative_to(ROOT)).replace("\\", "/"),
        "personalApis": [item["api"] for item in personal.get("apis", [])],
        "sellerApis": [item["api"] for item in seller.get("apis", [])],
        "personalError": personal.get("error"),
        "sellerError": seller.get("error"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

"""卖家工作台数据罗盘采集。"""
from __future__ import annotations

from src.scraper import launch_task_browser
from src.services.seller_datacompass_parser import SHORT_API_NAMES, parse_datacompass_api
from src.services.shop_datacompass_storage import upsert_snapshot
from src.utils import random_sleep

SELLER_DATA_URL = "https://seller.goofish.com/?site=COMMONPRO#/seller-data/data"
CYCLE_BUTTONS = [("1d", "近1天"), ("7d", "近7天"), ("30d", "近30天")]
DATACOMPASS_PREFIX = "mtop.alibaba.idle.seller.pc.datacompass."


async def _dismiss_overlays(page) -> None:
    for locator in (
        page.locator("text=近30天不再显示"),
        page.get_by_role("button", name="取消"),
        page.locator("button[aria-label='Close']"),
        page.locator("text=×").first,
    ):
        try:
            if await locator.count() > 0:
                await locator.first.click(timeout=1500)
                await page.wait_for_timeout(400)
        except Exception:
            continue
    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass


async def scrape_shop_datacompass(task_config: dict, debug_limit: int = 0) -> int:
    del debug_limit
    playwright, browser, context, state_file = await launch_task_browser(task_config)
    shop_name = None
    saved = 0
    page = await context.new_page()
    captured: dict[str, dict] = {}

    async def on_response(response):
        url = response.url
        if DATACOMPASS_PREFIX not in url and "datacompass.get.begin.time" not in url:
            return
        api_name = None
        for full_name in SHORT_API_NAMES:
            if full_name in url:
                api_name = full_name
                break
        if api_name is None:
            return
        try:
            payload = await response.json()
        except Exception:
            return
        captured[api_name] = payload

    page.on("response", on_response)
    try:
        await page.goto(
            "https://seller.goofish.com/?site=COMMONPRO",
            wait_until="domcontentloaded",
            timeout=45000,
        )
        await page.wait_for_timeout(2500)
        await _dismiss_overlays(page)
        await page.goto(SELLER_DATA_URL, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(6000)
        await _dismiss_overlays(page)

        async def persist_cycle(cycle: str) -> int:
            count = 0
            for api_name, payload in list(captured.items()):
                parsed = parse_datacompass_api(api_name, payload)
                if not parsed:
                    continue
                await upsert_snapshot(
                    account_state_file=state_file,
                    shop_name=shop_name,
                    time_cycle=cycle,
                    parsed=parsed,
                    raw=payload,
                )
                count += 1
                print(f"已保存 {cycle} / {parsed.get('api_name')}")
            return count

        saved += await persist_cycle("1d")
        for cycle, label in CYCLE_BUTTONS[1:]:
            captured.clear()
            locator = page.get_by_text(label, exact=True)
            try:
                if await locator.count() > 0:
                    await locator.first.click()
                    await page.wait_for_timeout(4000)
            except Exception:
                print(f"切换时间维度 {label} 失败，继续使用当前数据。")
            await random_sleep(1, 2)
            saved += await persist_cycle(cycle)
        print(f"店铺数据罗盘采集完成，共写入 {saved} 条快照。")
        return saved
    finally:
        page.remove_listener("response", on_response)
        await page.close()
        await browser.close()
        await playwright.stop()

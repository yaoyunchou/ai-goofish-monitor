"""笔记页采集。只使用小红书登录文件，不把登录态交给商品公开页。"""
from __future__ import annotations

import time
from dataclasses import dataclass

from src.domain.xhs_note_parse import NoteFields, parse_note_html

NOTE_GAP_SECONDS = 3
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class NoteFetch:
    status: int
    final_url: str
    body: str
    error: str | None = None


class NoteBrowser:
    """一轮笔记共用一个带 storage_state 的浏览器。"""

    def __init__(self, storage_state: str) -> None:
        self._storage_state = storage_state
        self._playwright = None
        self._browser = None
        self._context = None

    def __enter__(self) -> NoteBrowser:
        from playwright.sync_api import sync_playwright

        from src.config import LOGIN_IS_EDGE, RUN_HEADLESS

        self._playwright = sync_playwright().start()
        launch_args = ["--disable-blink-features=AutomationControlled", "--no-proxy-server"]
        channel = "msedge" if LOGIN_IS_EDGE else "chrome"
        try:
            self._browser = self._playwright.chromium.launch(
                headless=RUN_HEADLESS,
                channel=channel,
                args=launch_args,
            )
        except Exception:
            self._browser = self._playwright.chromium.launch(headless=RUN_HEADLESS, args=launch_args)
        self._context = self._browser.new_context(
            storage_state=self._storage_state,
            user_agent=_UA,
            locale="zh-CN",
            viewport={"width": 1280, "height": 900},
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for closer in (self._context, self._browser):
            if closer is not None:
                try:
                    closer.close()
                except Exception:
                    pass
        if self._playwright is not None:
            self._playwright.stop()

    def fetch(self, url: str) -> NoteFetch:
        page = self._context.new_page()
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1500)
            status = response.status if response is not None else 0
            return NoteFetch(status, page.url, page.content())
        except Exception as exc:
            return NoteFetch(0, url, "", str(exc))
        finally:
            page.close()


def open_notes(storage_state: str, urls: list[str], *, gap_seconds: float = NOTE_GAP_SECONDS) -> list[tuple[str, NoteFetch]]:
    results: list[tuple[str, NoteFetch]] = []
    with NoteBrowser(storage_state) as browser:
        for index, url in enumerate(urls):
            if index and gap_seconds:
                time.sleep(gap_seconds)
            results.append((url, browser.fetch(url)))
    return results


def fields_of(fetched: NoteFetch) -> NoteFields:
    if fetched.error and not fetched.body:
        return NoteFields(None, None, None, None, None, None, None, False)
    return parse_note_html(fetched.body, fetched.status)

"""小红书公开页采集。不携带 Cookie，不打开登录窗。

商品页是前端渲染的。直接下载 HTML 只有空壳，已售在页面画出来之后才有。
这里用单独的浏览器打开公开页，不加载闲鱼或小红书登录态。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.xhs_parse import is_short_link, parse_product_id, parse_public_html
from src.time_utils import shanghai_now

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
@dataclass(frozen=True)
class FetchResult:
    status: int
    final_url: str
    body: str
    error: str | None = None


@dataclass(frozen=True)
class CollectOutcome:
    product_id: str
    ok: bool
    sold: int | None = None
    price: float | None = None
    title: str | None = None
    shop_name: str | None = None
    cover_url: str | None = None
    final_url: str | None = None
    error: str | None = None
    blocked: bool = False
    skipped: bool = False
    delisted: bool = False
    captured_at: datetime | None = None
    note: str | None = None


class PublicBrowser:
    """一轮采集共用一个浏览器。上下文不带任何登录态。"""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._context = None

    def __enter__(self) -> PublicBrowser:
        from playwright.sync_api import sync_playwright

        from src.config import LOGIN_IS_EDGE, RUN_HEADLESS

        try:
            self._playwright = sync_playwright().start()
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-proxy-server",
            ]
            channel = "msedge" if LOGIN_IS_EDGE else "chrome"
            try:
                self._browser = self._playwright.chromium.launch(
                    headless=RUN_HEADLESS,
                    channel=channel,
                    args=launch_args,
                )
            except Exception:
                self._browser = self._playwright.chromium.launch(
                    headless=RUN_HEADLESS,
                    args=launch_args,
                )
            self._context = self._browser.new_context(
                user_agent=_UA,
                locale="zh-CN",
                viewport={"width": 1280, "height": 900},
            )
        except Exception:
            self.close()
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        for closer in (self._context, self._browser):
            if closer is None:
                continue
            try:
                closer.close()
            except Exception:
                pass
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._context = None
        self._browser = None
        self._playwright = None

    def fetch(self, url: str) -> FetchResult:
        page = self._context.new_page()
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            status = response.status if response is not None else 0
            try:
                page.wait_for_selector(".spu-text, .goods-name", timeout=15000)
            except Exception:
                pass
            return FetchResult(
                status=status,
                final_url=page.url or url,
                body=page.content(),
            )
        except Exception as exc:
            return FetchResult(status=0, final_url=url, body="", error=str(exc))
        finally:
            page.close()


def fetch_public(url: str) -> FetchResult:
    try:
        with PublicBrowser() as browser:
            return browser.fetch(url)
    except Exception as exc:
        return FetchResult(status=0, final_url=url, body="", error=str(exc))


def _is_note_link(url: str | None) -> bool:
    text = url or ""
    return "/discovery/" in text or "/explore/" in text


def _product_url(product_id: str, source_url: str | None) -> str:
    if source_url and source_url.startswith("http") and not is_short_link(source_url):
        # 笔记链接不是商品页，打开后会进登录墙，并把这一轮剩下的商品停掉。
        if "/discovery/" not in source_url and "/explore/" not in source_url:
            return source_url
    return f"https://www.xiaohongshu.com/goods-detail/{product_id}"


def collect_public_product(
    product_id: str,
    source_url: str | None,
    fetch,
    now: datetime | None = None,
) -> CollectOutcome:
    captured = now or shanghai_now()
    if _is_note_link(source_url):
        return CollectOutcome(
            product_id=product_id,
            ok=False,
            error="这是笔记链接，不是商品页，没有累计已售",
            final_url=source_url,
            captured_at=captured,
        )
    target = source_url if source_url and is_short_link(source_url) else _product_url(product_id, source_url)
    fetched = fetch(target)
    final_url = fetched.final_url or target
    resolved_id = parse_product_id(final_url) or product_id
    if resolved_id != product_id and is_short_link(target):
        product_id = resolved_id
    if fetched.status == 461:
        return CollectOutcome(
            product_id=product_id,
            ok=False,
            blocked=True,
            error="公开页返回 461，本轮停止，未使用登录态",
            final_url=final_url,
            captured_at=captured,
        )
    if fetched.error and not fetched.body:
        return CollectOutcome(
            product_id=product_id,
            ok=False,
            error=fetched.error,
            final_url=final_url,
            captured_at=captured,
        )
    fields = parse_public_html(fetched.body, fetched.status)
    if fields.delisted:
        return CollectOutcome(
            product_id=product_id,
            ok=False,
            delisted=True,
            title=fields.title,
            shop_name=fields.shop_name,
            cover_url=fields.cover_url,
            price=fields.price,
            error=fields.delist_reason or "商品已下架",
            final_url=final_url,
            captured_at=captured,
        )
    if fields.login_required or fields.sold is None and _looks_blocked(fetched.body):
        return CollectOutcome(
            product_id=product_id,
            ok=False,
            blocked=True,
            title=fields.title,
            shop_name=fields.shop_name,
            cover_url=fields.cover_url,
            error="公开页要求登录，本轮停止",
            final_url=final_url,
            captured_at=captured,
        )
    if fields.sold is None:
        return CollectOutcome(
            product_id=product_id,
            ok=False,
            title=fields.title,
            shop_name=fields.shop_name,
            cover_url=fields.cover_url,
            price=fields.price,
            error="公开页未解析到累计已售",
            final_url=final_url,
            captured_at=captured,
        )
    return CollectOutcome(
        product_id=product_id,
        ok=True,
        sold=fields.sold,
        price=fields.price,
        title=fields.title,
        shop_name=fields.shop_name,
        cover_url=fields.cover_url,
        final_url=final_url,
        captured_at=captured,
        note="public-html",
    )


def _looks_blocked(body: str) -> bool:
    text = body or ""
    return "请登录" in text or "扫码登录" in text


def collect_round(targets: list[dict], fetch=None, now: datetime | None = None) -> list[CollectOutcome]:
    """按顺序采集。遇到 461 或登录墙后，本轮剩余商品不再请求。"""
    if fetch is None:
        try:
            with PublicBrowser() as browser:
                return _collect_round(targets, browser.fetch, now)
        except Exception as exc:
            return [
                CollectOutcome(product_id=target["id"], ok=False, error=str(exc))
                for target in targets
            ]
    return _collect_round(targets, fetch, now)


def _collect_round(targets: list[dict], fetch, now: datetime | None) -> list[CollectOutcome]:
    outcomes: list[CollectOutcome] = []
    stopped = False
    for target in targets:
        product_id = target["id"]
        if stopped:
            outcomes.append(
                CollectOutcome(
                    product_id=product_id,
                    ok=False,
                    skipped=True,
                    error="本轮已因登录墙或 461 停止",
                )
            )
            continue
        outcome = collect_public_product(product_id, target.get("source_url"), fetch, now=now)
        outcomes.append(outcome)
        if outcome.blocked:
            stopped = True
    return outcomes

"""小红书公开页采集。不携带 Cookie，不打开登录窗。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.domain.xhs_parse import is_short_link, parse_product_id, parse_public_html
from src.time_utils import shanghai_now

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
_TIMEOUT = 20


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


def fetch_public(url: str) -> FetchResult:
    request = Request(url, headers={"User-Agent": _UA, "Accept": "text/html"})
    try:
        with urlopen(request, timeout=_TIMEOUT) as response:
            status = getattr(response, "status", 200) or 200
            final_url = response.geturl()
            body = response.read().decode("utf-8", errors="replace")
            return FetchResult(status=status, final_url=final_url, body=body)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return FetchResult(status=exc.code, final_url=url, body=body, error=str(exc))
    except URLError as exc:
        return FetchResult(status=0, final_url=url, body="", error=str(exc.reason))


def _product_url(product_id: str, source_url: str | None) -> str:
    if source_url and source_url.startswith("http") and not is_short_link(source_url):
        return source_url
    return f"https://www.xiaohongshu.com/goods-detail/{product_id}"


def collect_public_product(
    product_id: str,
    source_url: str | None,
    fetch,
    now: datetime | None = None,
) -> CollectOutcome:
    captured = now or shanghai_now()
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
    client = fetch or fetch_public
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
        outcome = collect_public_product(product_id, target.get("source_url"), client, now=now)
        outcomes.append(outcome)
        if outcome.blocked:
            stopped = True
    return outcomes

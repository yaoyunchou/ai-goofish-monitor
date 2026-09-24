"""从小红书公开链接里取出商品 ID，并从公开页 HTML 里取已售/价格。不处理登录态。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

_GOODS_ID = re.compile(
    r"(?:goods-detail|goods|item)/([0-9a-fA-F]{16,})",
    re.IGNORECASE,
)
_BARE_ID = re.compile(r"^[0-9a-fA-F]{16,}$")
_SOLD = re.compile(r'"(?:soldCount|sold_count|saleCount)"\s*:\s*(\d+)')
_SOLD_SPU = re.compile(
    r'class="spu-text"[^>]*>\s*已售\s*([0-9]+(?:\.[0-9]+)?)\s*(万)?'
)
_SOLD_TEXT = re.compile(r"已售\s*([0-9]+(?:\.[0-9]+)?)\s*(万)?")
_PRICE = re.compile(r'"(?:price|salePrice)"\s*:\s*(\d+(?:\.\d+)?)')
_TITLE = re.compile(r"<title>([^<]{1,120})</title>", re.IGNORECASE)
_GOODS_NAME = re.compile(r'class="goods-name"[^>]*>\s*([^<]{1,200})')
_SELLER_NAME = re.compile(r'class="seller-name"[^>]*>\s*([^<]{1,80})')
_COVER = re.compile(r'"(?:cover|image|mainImage)"\s*:\s*"(https:[^"]+)"')
_COVER_IMG = re.compile(
    r'<img\b[^>]*class="carousel-image"[^>]*>',
    re.IGNORECASE,
)
_GENERIC_TITLES = {"小红书", "商品详情"}
_LOGIN_MARKERS = ("登录后", "请登录", "扫码登录", "login-container")


_SHOP = re.compile(r'"(?:shopName|sellerName|vendorName)"\s*:\s*"([^"\\]{1,80})"')


@dataclass(frozen=True)
class PublicFields:
    sold: int | None
    price: float | None
    title: str | None
    cover_url: str | None
    shop_name: str | None
    login_required: bool
    delisted: bool = False
    delist_reason: str | None = None


def parse_product_id(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if _BARE_ID.match(raw):
        return raw.lower()
    match = _GOODS_ID.search(raw)
    if match:
        return match.group(1).lower()
    return None


def is_short_link(text: str) -> bool:
    host = urlparse(text.strip()).netloc.lower()
    return "xhslink.com" in host


def is_note_link(text: str) -> bool:
    raw = (text or "").lower()
    return "/discovery/item/" in raw or "/explore/" in raw


def parse_public_html(html: str, status_code: int = 200) -> PublicFields:
    body = html or ""
    if status_code == 461:
        return PublicFields(None, None, None, None, None, login_required=True)
    price = _parse_price(body)
    title = _parse_title(body)
    cover = _parse_cover(body)
    shop = _parse_shop(body)
    reason = _delist_reason(body)
    if reason:
        return PublicFields(None, price, title, cover, shop, False, True, reason)
    sold = _parse_sold(body)
    login_required = sold is None and any(marker in body for marker in _LOGIN_MARKERS)
    return PublicFields(sold, price, title, cover, shop, login_required)


def _delist_reason(html: str) -> str | None:
    if "当前商品违规" in html or "违规，无法展示" in html:
        return "违规下架"
    markers = ("已下架", "商品不存在", "商品已失效", "unBuyableGoShop")
    if any(marker in html for marker in markers):
        return "商品已下架"
    return None


def _sold_from_match(match: re.Match[str] | None) -> int | None:
    if match is None:
        return None
    value = float(match.group(1))
    if match.lastindex and match.lastindex >= 2 and match.group(2):
        value *= 10000
    return int(value)


def _parse_sold(html: str) -> int | None:
    match = _SOLD.search(html)
    if match:
        return int(match.group(1))
    rendered = _sold_from_match(_SOLD_SPU.search(html))
    if rendered is not None:
        return rendered
    return _sold_from_match(_SOLD_TEXT.search(html))


def _parse_price(html: str) -> float | None:
    match = _PRICE.search(html)
    if match:
        return float(match.group(1))
    start = html.find('class="price"')
    if start < 0:
        return None
    open_end = html.find(">", start)
    if open_end < 0:
        return None
    end = html.find('class="spu-text"', open_end)
    chunk = html[open_end + 1:end if end > open_end else open_end + 400]
    text = re.sub(r"<[^>]+>", "", chunk)
    text = re.sub(r"\s+", "", text)
    found = re.search(r"(\d+(?:\.\d+)?)", text)
    if not found:
        return None
    return float(found.group(1))


def _parse_title(html: str) -> str | None:
    rendered = _GOODS_NAME.search(html)
    if rendered:
        title = rendered.group(1).strip()
        if title:
            return title
    match = _TITLE.search(html)
    if not match:
        return None
    title = match.group(1).strip()
    if not title or title in _GENERIC_TITLES:
        return None
    return title


def _parse_shop(html: str) -> str | None:
    rendered = _SELLER_NAME.search(html)
    if rendered:
        name = rendered.group(1).strip()
        if name:
            return name
    match = _SHOP.search(html)
    if not match:
        return None
    return match.group(1).strip() or None


def _parse_cover(html: str) -> str | None:
    match = _COVER.search(html)
    if match:
        return match.group(1).replace("\\u002F", "/").replace("\\/", "/")
    tag = _COVER_IMG.search(html)
    if tag is None:
        return None
    src = re.search(r'\bsrc="([^"]+)"', tag.group(0))
    if src is None:
        return None
    return src.group(1).replace("\\u002F", "/").replace("\\/", "/")

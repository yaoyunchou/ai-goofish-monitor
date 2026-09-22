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
_SOLD_TEXT = re.compile(r"已售\s*([0-9]+(?:\.[0-9]+)?)\s*(万)?")
_PRICE = re.compile(r'"(?:price|salePrice)"\s*:\s*(\d+(?:\.\d+)?)')
_TITLE = re.compile(r"<title>([^<]{1,120})</title>", re.IGNORECASE)
_COVER = re.compile(r'"(?:cover|image|mainImage)"\s*:\s*"(https:[^"]+)"')
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


def _parse_sold(html: str) -> int | None:
    match = _SOLD.search(html)
    if match:
        return int(match.group(1))
    text = _SOLD_TEXT.search(html)
    if not text:
        return None
    value = float(text.group(1))
    if text.group(2):
        value *= 10000
    return int(value)


def _parse_price(html: str) -> float | None:
    match = _PRICE.search(html)
    if not match:
        return None
    return float(match.group(1))


def _parse_title(html: str) -> str | None:
    match = _TITLE.search(html)
    if not match:
        return None
    title = match.group(1).strip()
    return title or None


def _parse_shop(html: str) -> str | None:
    match = _SHOP.search(html)
    if not match:
        return None
    return match.group(1).strip() or None


def _parse_cover(html: str) -> str | None:
    match = _COVER.search(html)
    if not match:
        return None
    return match.group(1).replace("\\u002F", "/").replace("\\/", "/")

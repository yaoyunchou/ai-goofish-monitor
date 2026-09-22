"""小红书高水位与公开页解析。"""
from datetime import datetime

from src.domain.xhs_analytics import (
    SnapshotPoint,
    delta_between,
    high_water,
    window_stats,
)
from src.domain.xhs_parse import is_short_link, parse_product_id, parse_public_html
from src.time_utils import SHANGHAI_TZ
from src.xhs_collector import FetchResult, collect_round


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=SHANGHAI_TZ)


def test_smaller_reading_does_not_lower_high_water():
    points = [
        SnapshotPoint(at("2026-09-21T09:00:00"), 500),
        SnapshotPoint(at("2026-09-22T09:00:00"), 600),
        SnapshotPoint(at("2026-09-22T16:00:00"), 80),
        SnapshotPoint(at("2026-09-23T12:00:00"), 700),
    ]
    assert high_water(points, at("2026-09-22T16:30:00")) == 600
    stats = window_stats(points, at("2026-09-23T12:30:00"))
    assert stats["sold_total"] == 700
    assert stats["today"] == 100


def test_midnight_boundary_is_not_counted_twice():
    points = [
        SnapshotPoint(at("2026-09-21T16:00:00"), 990),
        SnapshotPoint(at("2026-09-22T00:00:00"), 1000),
        SnapshotPoint(at("2026-09-22T10:00:00"), 1030),
    ]
    stats = window_stats(points, at("2026-09-22T10:30:00"))
    assert stats["today"] == 30
    assert stats["today_incomplete"] is False
    assert stats["yesterday"] == 10
    assert stats["today"] + stats["yesterday"] == 40


def test_missing_baseline_is_none_not_zero():
    points = [
        SnapshotPoint(at("2026-09-21T12:00:00"), None),
        SnapshotPoint(at("2026-09-22T12:00:00"), 10),
    ]
    delta = delta_between(points, at("2026-09-21T00:00:00"), at("2026-09-22T18:00:00"))
    assert delta.delta is None


def test_midday_start_uses_first_snapshot_and_marks_incomplete():
    points = [
        SnapshotPoint(at("2026-09-22T09:00:00"), 1000, 10),
        SnapshotPoint(at("2026-09-22T12:00:00"), 1080, 10),
        SnapshotPoint(at("2026-09-22T16:00:00"), 1200, 12),
    ]
    stats = window_stats(points, at("2026-09-22T16:30:00"))
    assert stats["today"] == 200
    assert stats["today_incomplete"] is True
    assert stats["today_fuzzy"] == 2400


def test_same_day_splits_when_midnight_baseline_exists():
    points = [
        SnapshotPoint(at("2026-09-21T23:00:00"), 980, 10),
        SnapshotPoint(at("2026-09-22T09:00:00"), 1000, 10),
        SnapshotPoint(at("2026-09-22T12:00:00"), 1080, 10),
        SnapshotPoint(at("2026-09-22T16:00:00"), 1200, 12),
    ]
    stats = window_stats(points, at("2026-09-22T16:30:00"))
    assert stats["sold_total"] == 1200
    assert stats["today"] == 220
    assert stats["today_incomplete"] is False


def test_parse_product_id_from_goods_link_and_bare_id():
    link = "https://www.xiaohongshu.com/goods-detail/64F1AABBCCDDEEFF00112233?foo=1"
    assert parse_product_id(link) == "64f1aabbccddeeff00112233"
    assert parse_product_id("64f1aabbccddeeff00112233") == "64f1aabbccddeeff00112233"
    assert parse_product_id("https://xhslink.com/a/abc") is None
    assert is_short_link("https://xhslink.com/a/abc") is True


def test_parse_public_html_sold_and_login_wall():
    page = '<title>示例商品</title> "soldCount": 42 "price": 19.9 "shopName": "示例店"'
    fields = parse_public_html(page)
    assert fields.sold == 42
    assert fields.price == 19.9
    assert fields.shop_name == "示例店"
    assert fields.login_required is False
    blocked = parse_public_html("<div>请登录</div>", status_code=461)
    assert blocked.login_required is True
    assert blocked.sold is None
    assert parse_public_html("<div>当前商品已下架，进店逛逛</div>").delist_reason == "商品已下架"
    assert parse_public_html("<div>当前商品违规，无法展示</div>").delist_reason == "违规下架"


def test_collect_round_stops_after_461_without_login():
    calls = []

    def fetch(url: str) -> FetchResult:
        calls.append(url)
        if len(calls) == 1:
            return FetchResult(status=461, final_url=url, body="")
        return FetchResult(status=200, final_url=url, body='"soldCount": 1')

    outcomes = collect_round(
        [
            {"id": "64f1aabbccddeeff00112233", "source_url": "https://www.xiaohongshu.com/goods-detail/64f1aabbccddeeff00112233"},
            {"id": "64f1aabbccddeeff00112234", "source_url": "https://www.xiaohongshu.com/goods-detail/64f1aabbccddeeff00112234"},
        ],
        fetch=fetch,
    )
    assert len(calls) == 1
    assert outcomes[0].blocked is True
    assert outcomes[1].skipped is True
    assert outcomes[0].sold is None


def test_collect_round_keeps_going_after_delist():
    calls = []

    def fetch(url: str) -> FetchResult:
        calls.append(url)
        if len(calls) == 1:
            return FetchResult(status=200, final_url=url, body="<title>旧款</title>当前商品已下架")
        return FetchResult(status=200, final_url=url, body='"soldCount": 8')

    outcomes = collect_round(
        [
            {"id": "64f1aabbccddeeff00112233", "source_url": "https://www.xiaohongshu.com/goods-detail/64f1aabbccddeeff00112233"},
            {"id": "64f1aabbccddeeff00112234", "source_url": "https://www.xiaohongshu.com/goods-detail/64f1aabbccddeeff00112234"},
        ],
        fetch=fetch,
    )
    assert len(calls) == 2
    assert outcomes[0].delisted is True
    assert outcomes[0].blocked is False
    assert outcomes[1].ok is True
    assert outcomes[1].sold == 8

from src.domain.seller_ids import (
    DEFAULT_SELLER_SUBSCRIPTION_ITEM_LIMIT,
    extract_seller_user_id,
    has_want_and_view,
    parse_seller_user_ids,
)
from src.seller_subscription_scraper import _resolve_item_limit
from src.infrastructure.persistence.db_connection import DbConnection
from src.services.seller_datacompass_parser import parse_banner_metrics, parse_datacompass_api


def test_parse_seller_user_ids_from_urls_and_numbers():
    values = parse_seller_user_ids(
        "https://www.goofish.com/personal?userId=2221197154547\n1234567890,2221197154547"
    )
    assert values == ["2221197154547", "1234567890"]


def test_extract_seller_user_id():
    assert extract_seller_user_id("2221197154547") == "2221197154547"
    assert extract_seller_user_id("https://www.goofish.com/personal?userId=2221197154547") == "2221197154547"
    assert extract_seller_user_id("not-a-user") is None


def test_default_seller_subscription_item_limit():
    assert DEFAULT_SELLER_SUBSCRIPTION_ITEM_LIMIT == 100


def test_resolve_item_limit_from_task_config():
    assert _resolve_item_limit({}) == 100
    assert _resolve_item_limit({"item_limit": 50}) == 50
    assert _resolve_item_limit({"item_limit": "bad"}) == 100
    assert _resolve_item_limit({"item_limit": 0}) == 1


def test_has_want_and_view_filter():
    assert has_want_and_view({"“想要”人数": 0, "浏览量": 3}) is True
    assert has_want_and_view({"“想要”人数": "NaN", "浏览量": 3}) is False
    assert has_want_and_view({"“想要”人数": 1, "浏览量": "-"}) is False
    assert has_want_and_view({"“想要”人数": 1}) is False


def test_parse_banner_metrics():
    raw = {
        "data": {
            "extendInfo": {"realDateRange": ["20260914", "20260914"]},
            "data": {
                "graphBannerBenchData": {
                    "bannerDataList": [
                        {"name": "showPv", "data": 76, "lastData": 72, "ratio": 0.0556, "ratioFormat": "5.56%"},
                    ]
                }
            },
        }
    }
    parsed = parse_banner_metrics(raw)
    assert parsed["metrics"]["showPv"]["value"] == 76
    parsed_api = parse_datacompass_api(
        "mtop.alibaba.idle.seller.pc.datacompass.singleuser.seller.summary",
        raw,
    )
    assert parsed_api["api_name"] == "seller.summary"


def test_adapt_sql_keeps_postgres_type_cast():
    adapter = DbConnection(None)
    sql = adapter._adapt_sql(
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS seller_user_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    assert "::jsonb" in sql
    assert "%(jsonb)s" not in sql
    named = adapter._adapt_sql("SELECT * FROM tasks WHERE id = :id")
    assert named == "SELECT * FROM tasks WHERE id = %(id)s"

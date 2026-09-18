from src.services.seller_subscription_storage import _summarize_subscription_record


def test_summarize_subscription_record_empty():
    summary = _summarize_subscription_record(None)
    assert summary["has_record"] is False
    assert summary["image_count"] == 0


def test_summarize_subscription_record_with_product():
    record = {
        "爬取时间": "2026-09-16T10:00:00",
        "任务类型": "seller_subscription",
        "任务名称": "seller_subscriptions",
        "商品信息": {
            "商品ID": "123",
            "商品标题": "测试商品",
            "商品描述": "hello",
            "商品图片列表": ["https://img.example/1.jpg", "https://img.example/2.jpg"],
        },
        "卖家信息": {"卖家ID": "999", "卖家昵称": "卖家A"},
    }
    summary = _summarize_subscription_record(record)
    assert summary["has_record"] is True
    assert summary["image_count"] == 2
    assert summary["description_length"] == 5
    assert "商品ID" in summary["product_fields"]
    assert summary["seller_fields"] == ["卖家ID", "卖家昵称"]
    assert summary["has_sku_data"] is False

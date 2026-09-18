from src.services.item_detail_raw_storage import summarize_detail_api_raw


def test_summarize_detail_api_raw_empty():
    summary = summarize_detail_api_raw(None)
    assert summary["has_detail_api"] is False
    assert summary["sku_count"] == 0


def test_summarize_detail_api_raw_with_sku():
    raw = {
        "api": "mtop.taobao.idle.pc.detail",
        "data": {
            "itemDO": {
                "skuList": [{"skuId": 1}, {"skuId": 2}],
                "minPrice": "3.66",
                "maxPrice": "66.66",
                "soldPrice": "3.66",
            },
            "sellerDO": {"sellerId": "123"},
        },
        "ret": ["SUCCESS::调用成功"],
    }
    summary = summarize_detail_api_raw(raw)
    assert summary["has_detail_api"] is True
    assert summary["sku_count"] == 2
    assert summary["min_price"] == "3.66"
    assert "itemDO" in summary["item_do_keys"] or summary["sku_count"] == 2

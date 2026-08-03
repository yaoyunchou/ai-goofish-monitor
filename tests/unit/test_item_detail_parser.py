import pytest

from src.item_detail_parser import (
    extract_skus_from_detail_payloads,
    parse_title_sku_fragments,
)


@pytest.mark.asyncio
async def test_extract_skus_from_sku_list():
    payloads = [
        {
            "data": {
                "itemDO": {"title": "demo", "itemId": "1"},
                "skuList": [
                    {
                        "skuId": "111",
                        "price": "2580",
                        "propertyList": [
                            {"propertyText": "颜色", "valueText": "白色"},
                            {"propertyText": "长度", "valueText": "2m"},
                        ],
                    },
                    {
                        "skuId": "222",
                        "price": "3080",
                        "propertyList": [
                            {"propertyText": "颜色", "valueText": "黑色"},
                        ],
                    },
                ],
            }
        }
    ]
    skus = await extract_skus_from_detail_payloads(payloads, fallback_title="demo")
    assert len(skus) == 2
    assert skus[0]["sku_id"] == "111"
    assert skus[0]["price"] == 2580.0


def test_parse_title_sku_fragments():
    fragments = parse_title_sku_fragments("标题 颜色分类: 白色、长度: 2m")
    assert len(fragments) == 2
    assert fragments[0]["name"] == "颜色分类"

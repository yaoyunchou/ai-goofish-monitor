from src.services.listing_ai_filter import (
    _normalize_filter_response,
    build_filter_analysis_result,
    heuristic_listing_filter,
)


def test_heuristic_rejects_cable_style_title():
    record = {
        "商品信息": {
            "商品标题": (
                "机乐堂适用苹果16充电线器iPhone14数据线13手机pd 30w快充"
                " 长度: 2m、颜色分类: 冰晶白"
            )
        }
    }
    result = heuristic_listing_filter(record)
    assert result is not None
    assert result["is_target_product"] is False
    assert result["detected_category"] == "data_cable_only"


def test_heuristic_allows_charger_title():
    record = {
        "商品信息": {
            "商品标题": "机乐堂30W氮化镓充电头 冰晶白 PD快充",
        }
    }
    assert heuristic_listing_filter(record) is None


def test_normalize_filter_response_maps_cable_to_false():
    payload = _normalize_filter_response(
        {
            "is_target_product": False,
            "detected_category": "data_cable_only",
            "reason": "主图为线缆",
        }
    )
    assert payload["is_target_product"] is False
    assert payload["detected_category"] == "data_cable_only"


def test_build_filter_analysis_result_enriches_cable_reason():
    result = build_filter_analysis_result(
        {
            "is_target_product": False,
            "detected_category": "data_cable_only",
            "reason": "主图为线缆",
        }
    )
    assert result["is_recommended"] is False
    assert result["analysis_source"] == "ai_filter"
    assert "数据线" in result["reason"]

from src.services.listing_ai_filter import (
    _normalize_filter_response,
    build_filter_analysis_result,
)


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

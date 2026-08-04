from src.search_response_utils import (
    extract_search_result_list,
    summarize_search_payload,
    unwrap_mtop_data,
)


def test_unwrap_mtop_data_parses_json_string():
    inner = {"resultList": [{"id": 1}]}
    payload = {"ret": ["SUCCESS::调用成功"], "data": '{"resultList":[{"id":1}]}'}
    assert unwrap_mtop_data(payload) == inner


def test_extract_search_result_list_from_nested_data_object():
    payload = {
        "data": {
            "resultList": [{"data": {"item": {"main": {}}}}],
        }
    }
    assert len(extract_search_result_list(payload)) == 1


def test_extract_search_result_list_empty_when_missing():
    assert extract_search_result_list({"data": {}}) == []
    assert extract_search_result_list({"ret": ["FAIL"]}) == []


def test_summarize_search_payload_includes_ret_and_keys():
    text = summarize_search_payload(
        {"ret": ["SUCCESS::ok"], "data": {"resultList": [], "foo": 1}}
    )
    assert "ret=" in text
    assert "resultList=0" in text or "resultList=missing" in text
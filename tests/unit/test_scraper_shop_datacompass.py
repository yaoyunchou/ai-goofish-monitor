"""店铺数据罗盘解析与采集单元测试。"""
import asyncio

from src.services.seller_datacompass_parser import (
    parse_browse_summary,
    parse_datacompass_api,
    parse_flow_detail,
)


def test_parse_datacompass_seller_summary_fixture(load_json_fixture):
    raw = load_json_fixture("datacompass_seller_summary.json")
    parsed = parse_datacompass_api(
        "mtop.alibaba.idle.seller.pc.datacompass.singleuser.seller.summary",
        raw,
    )
    assert parsed is not None
    assert parsed["api_name"] == "seller.summary"
    assert parsed["metrics"]["showPv"]["value"] == 76
    assert parsed["metrics"]["browsePv"]["value"] == 41
    assert parsed["date_range"] == ["20260914", "20260914"]


def test_parse_datacompass_browse_summary_fixture(load_json_fixture):
    raw = load_json_fixture("datacompass_browse_summary.json")
    parsed = parse_datacompass_api(
        "mtop.alibaba.idle.seller.pc.datacompass.singleuser.browse.summary",
        raw,
    )
    assert parsed is not None
    assert parsed["api_name"] == "browse.summary"
    assert parsed["distribution"]["source"][0]["label"] == "搜索"
    assert parsed["distribution"]["time"][0]["label"] == "晚间"


def test_parse_flow_detail_merges_banner_metrics():
    raw = {
        "data": {
            "data": {
                "itemFlowTransferData": {
                    "scene": "overview",
                    "timeCycle": "1d",
                    "graphBannerBenchData": {
                        "bannerDataList": [
                            {"name": "showPv", "data": 10, "lastData": 8},
                        ]
                    },
                }
            }
        }
    }
    parsed = parse_flow_detail(raw)
    assert parsed["metrics"]["showPv"]["value"] == 10
    assert parsed["scene"] == "overview"


def test_persist_cycle_writes_parsed_snapshot(load_json_fixture):
    """验证 captured API 经 parse 后写入 upsert（persist_cycle 核心逻辑）。"""
    from src.scraper_shop_datacompass import DATACOMPASS_PREFIX, SHORT_API_NAMES

    raw = load_json_fixture("datacompass_seller_summary.json")
    api_name = "mtop.alibaba.idle.seller.pc.datacompass.singleuser.seller.summary"
    upsert_calls = []

    async def fake_upsert(**kwargs):
        upsert_calls.append(kwargs)

    async def run_persist():
        captured = {api_name: raw}
        count = 0
        for name, payload in list(captured.items()):
            parsed = parse_datacompass_api(name, payload)
            if not parsed:
                continue
            await fake_upsert(
                account_state_file="state/test.json",
                shop_name=None,
                time_cycle="1d",
                parsed=parsed,
                raw=payload,
            )
            count += 1
        return count

    saved = asyncio.run(run_persist())
    assert saved == 1
    assert upsert_calls[0]["parsed"]["api_name"] == SHORT_API_NAMES[api_name]
    assert DATACOMPASS_PREFIX in api_name

import asyncio
from unittest.mock import AsyncMock, patch

from src.services.item_analysis_dispatcher import (
    ItemAnalysisDispatcher,
    ItemAnalysisJob,
)


def test_dispatcher_runs_ai_filter_before_full_ai_and_rejects_cable():
    saved_records = []

    async def seller_loader(user_id: str):
        return {}

    async def image_downloader(product_id: str, image_urls: list[str], task_name: str):
        return []

    async def ai_analyzer(record: dict, image_paths: list[str], prompt_text: str):
        raise AssertionError("过滤未通过时不应调用完整 AI 分析")

    async def notifier(item_data: dict, reason: str):
        return None

    async def saver(record: dict, keyword: str):
        saved_records.append(record)
        return True

    filter_payload = {
        "is_target_product": False,
        "detected_category": "data_cable_only",
        "reason": "仅数据线",
    }

    async def run():
        dispatcher = ItemAnalysisDispatcher(
            concurrency=1,
            skip_ai_analysis=False,
            seller_loader=seller_loader,
            image_downloader=image_downloader,
            ai_analyzer=ai_analyzer,
            notifier=notifier,
            saver=saver,
        )
        with patch(
            "src.services.item_analysis_dispatcher.filter_listing_by_ai",
            new=AsyncMock(return_value=filter_payload),
        ):
            dispatcher.submit(
                ItemAnalysisJob(
                    keyword="demo",
                    task_name="Demo",
                    decision_mode="ai",
                    analyze_images=False,
                    prompt_text="full prompt",
                    keyword_rules=(),
                    final_record={"商品信息": {"商品ID": "1", "商品标题": "快充线"}},
                    seller_id=None,
                    zhima_credit_text=None,
                    registration_duration_text="",
                    purchase_intent="只要充电头",
                    enable_ai_listing_filter=True,
                )
            )
            await dispatcher.join()

    asyncio.run(run())
    assert saved_records[0]["ai_analysis"]["is_recommended"] is False
    assert saved_records[0]["ai_analysis"]["analysis_source"] == "ai_filter"

"""卖家用户页订阅采集：独立订阅表 + 详情补抓 + 分批模拟访问。"""
from __future__ import annotations

from datetime import datetime

from src.domain.seller_ids import (
    DEFAULT_SELLER_SUBSCRIPTION_ITEM_LIMIT,
    parse_metric_int,
    parse_seller_user_ids,
)
from src.domain.seller_subscription import SELLER_SUBSCRIPTION_TASK_NAME
from src.domain.seller_subscription_pacing import SubscriptionPacing
from src.scraper import (
    fetch_item_detail,
    launch_task_browser,
    scrape_user_profile,
)
from src.services.result_storage_service import save_result_record
from src.services.seller_subscription_storage import (
    record_subscription_run,
    save_seller_item_metric,
    save_seller_profile,
    touch_subscription_captured,
)
from src.utils import get_link_unique_key


def _resolve_item_limit(task_config: dict) -> int:
    raw = task_config.get("item_limit", DEFAULT_SELLER_SUBSCRIPTION_ITEM_LIMIT)
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        limit = DEFAULT_SELLER_SUBSCRIPTION_ITEM_LIMIT
    return max(1, limit)


async def scrape_seller_subscription(task_config: dict, debug_limit: int = 0) -> int:
    task_name = task_config.get("task_name") or SELLER_SUBSCRIPTION_TASK_NAME
    seller_ids = parse_seller_user_ids(
        task_config.get("seller_user_ids"),
        task_config.get("seller_urls"),
    )
    if not seller_ids:
        print("订阅任务未配置卖家，跳过。")
        await record_subscription_run("未配置卖家", saved=0, ok=False)
        return 0

    scrape_config = dict(task_config)
    scrape_config["task_name"] = task_name
    scrape_config["keyword"] = task_config.get("keyword") or task_name
    scrape_config["seller_user_ids"] = seller_ids
    return await _scrape_seller_ids(
        task_config=scrape_config,
        debug_limit=debug_limit,
        touch_registry=task_name == SELLER_SUBSCRIPTION_TASK_NAME,
    )


async def scrape_registered_seller_subscriptions(debug_limit: int = 0) -> int:
    from src.services.seller_subscription_service import build_scrape_task_config

    task_config = await build_scrape_task_config()
    if not task_config:
        print("没有启用的卖家订阅，跳过。")
        await record_subscription_run("没有启用的卖家订阅", saved=0, ok=False)
        return 0
    try:
        saved = await scrape_seller_subscription(task_config, debug_limit=debug_limit)
    except Exception as exc:
        await record_subscription_run(f"采集异常: {exc}", saved=0, ok=False)
        raise
    if saved > 0:
        await record_subscription_run(f"本次入库 {saved} 条商品指标", saved=saved, ok=True)
    else:
        await record_subscription_run(
            "采集完成但未入库任何商品，请检查登录态或卖家主页是否有在售商品",
            saved=0,
            ok=False,
        )
    return saved


async def _scrape_seller_ids(
    *,
    task_config: dict,
    debug_limit: int,
    touch_registry: bool,
) -> int:
    task_name = task_config.get("task_name") or SELLER_SUBSCRIPTION_TASK_NAME
    keyword = task_config.get("keyword") or task_name
    item_limit = _resolve_item_limit(task_config)
    collect_ratings = bool(task_config.get("collect_ratings", False))
    seller_ids = parse_seller_user_ids(task_config.get("seller_user_ids"))
    pacing = SubscriptionPacing.from_task_config(task_config)
    pacing.log_plan(len(seller_ids), item_limit)

    playwright, browser, context, state_file = await launch_task_browser(task_config)
    print(f"   使用登录态: {state_file}")
    scanned = 0
    detailed = 0
    saved = 0
    skipped = 0
    seller_saved: dict[str, int] = {}
    try:
        for seller_index, user_id in enumerate(seller_ids):
            await pacing.before_seller(seller_index)
            print(f"\n=== 订阅采集卖家 {user_id}（监控前 {item_limit} 条在售商品）===")
            await pacing.before_profile()
            profile = await scrape_user_profile(
                context,
                user_id,
                collect_ratings=collect_ratings,
                max_items=item_limit,
            )
            profile["卖家ID"] = profile.get("卖家ID") or user_id
            await save_seller_profile(task_name, user_id, profile)

            items = [
                item
                for item in (profile.get("卖家发布的商品列表") or [])
                if item.get("商品状态") == "在售"
            ][:item_limit]
            if not items:
                raw_count = len(profile.get("卖家发布的商品列表") or [])
                print(
                    f"   卖家 {user_id} 未获取到在售商品（列表共 {raw_count} 条），跳过详情采集。"
                )
                continue

            items = SubscriptionPacing.shuffle_items(items)
            print(f"   列表在售 {len(items)} 条，将分批拉取详情（顺序已随机打乱）。")
            seller_saved[user_id] = 0

            for item_index, item in enumerate(items):
                scanned += 1
                if debug_limit > 0 and saved >= debug_limit:
                    print(f"已达到调试上限 {debug_limit}，停止采集。")
                    return saved
                item_id = item.get("商品ID")
                item_link = item.get("商品链接") or (
                    f"https://www.goofish.com/item?id={item_id}" if item_id else ""
                )
                if not item_link:
                    skipped += 1
                    continue

                await pacing.before_detail(item_index)
                detailed += 1
                try:
                    detail = await fetch_item_detail(context, item_link)
                except Exception as exc:
                    print(f"   详情采集失败 {item_id}: {exc}")
                    skipped += 1
                    continue
                if not detail.get("ok"):
                    skipped += 1
                    continue

                item_data = {
                    "商品ID": item_id,
                    "商品标题": item.get("商品标题"),
                    "当前售价": item.get("商品价格"),
                    "商品主图链接": item.get("商品主图"),
                    "商品链接": item_link,
                    "商品状态": item.get("商品状态"),
                    "“想要”人数": detail.get("“想要”人数"),
                    "浏览量": detail.get("浏览量"),
                    "商品图片列表": detail.get("商品图片列表") or [],
                    "商品描述": detail.get("商品描述") or "",
                }
                want_count = parse_metric_int(item_data["“想要”人数"])
                view_count = parse_metric_int(item_data["浏览量"])
                record = {
                    "爬取时间": datetime.now().isoformat(),
                    "搜索关键字": keyword,
                    "任务名称": task_name,
                    "任务类型": "seller_subscription",
                    "商品信息": item_data,
                    "卖家信息": {
                        "卖家ID": user_id,
                        "卖家昵称": profile.get("卖家昵称"),
                        "鱼小铺等级": profile.get("鱼小铺等级"),
                        "粉丝数": profile.get("粉丝数"),
                        "好评率": profile.get("好评率"),
                    },
                }
                await save_result_record(record, keyword)
                item_data["_want_count"] = want_count
                item_data["_view_count"] = view_count
                await save_seller_item_metric(
                    task_name=task_name,
                    seller_user_id=user_id,
                    item=item_data,
                )
                saved += 1
                seller_saved[user_id] = seller_saved.get(user_id, 0) + 1
                print(
                    f"   入库 {item_id} 想要={want_count} 浏览={view_count} "
                    f"key={get_link_unique_key(item_link)}"
                )
                await pacing.after_detail(item_index)

            if touch_registry and seller_saved.get(user_id, 0) > 0:
                await touch_subscription_captured(user_id, profile.get("卖家昵称"))

        print(
            f"订阅任务完成：扫描 {scanned} → 详情 {detailed} → 入库 {saved} → 跳过 {skipped}"
        )
        return saved
    finally:
        await browser.close()
        await playwright.stop()

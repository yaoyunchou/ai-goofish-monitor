"""卖家订阅业务：独立于任务管理的订阅 CRUD 与调度配置。"""

from __future__ import annotations



from src.domain.models.task import TASK_TYPE_SELLER_SUBSCRIPTION

from src.domain.seller_ids import parse_seller_user_ids

from src.domain.seller_subscription import (

    SELLER_SUBSCRIPTION_TASK_NAME,

    SellerSubscriptionCreate,

    SellerSubscriptionScheduleUpdate,

    SellerSubscriptionUpdate,

    enrich_schedule,

    resolve_schedule_run_headless,

)

from src.infrastructure.persistence.task_repository_factory import create_task_repository

from src.services.seller_subscription_storage import (

    add_subscription,

    delete_subscription,

    get_schedule,

    get_subscription,

    list_enabled_seller_ids,

    list_subscriptions,

    update_schedule,

    update_subscription,

)





async def list_subscription_overview() -> dict:

    items = await list_subscriptions()

    schedule = enrich_schedule(await get_schedule())

    return {"items": items, "schedule": schedule}





async def create_subscription(payload: SellerSubscriptionCreate) -> dict:

    seller_user_id = payload.resolved_user_id()

    if not seller_user_id:

        raise ValueError("无法解析卖家 userId，请粘贴正确的用户主页链接")

    seller_url = (payload.seller_url or "").strip() or None

    row = await add_subscription(

        seller_user_id=seller_user_id,

        seller_url=seller_url,

        note=(payload.note or "").strip(),

    )

    return row





async def patch_subscription(subscription_id: int, payload: SellerSubscriptionUpdate) -> dict:

    existing = await get_subscription(subscription_id)

    if not existing:

        raise ValueError("订阅不存在")

    updated = await update_subscription(

        subscription_id,

        **payload.model_dump(exclude_unset=True),

    )

    return updated or existing





async def remove_subscription(subscription_id: int) -> None:

    if not await delete_subscription(subscription_id):

        raise ValueError("订阅不存在")





async def patch_schedule(payload: SellerSubscriptionScheduleUpdate) -> dict:

    schedule = await update_schedule(**payload.model_dump(exclude_unset=True))

    return enrich_schedule(schedule)





async def build_scrape_task_config() -> dict | None:

    schedule = await get_schedule()

    seller_ids = await list_enabled_seller_ids()

    if not seller_ids:

        return None

    return {

        "task_name": SELLER_SUBSCRIPTION_TASK_NAME,

        "keyword": SELLER_SUBSCRIPTION_TASK_NAME,

        "task_type": TASK_TYPE_SELLER_SUBSCRIPTION,

        "item_limit": schedule.get("item_limit") or 100,

        "collect_ratings": bool(schedule.get("collect_ratings")),

        "seller_user_ids": seller_ids,

        "account_state_file": schedule.get("account_state_file"),

        "account_strategy": schedule.get("account_strategy") or "auto",
        "pacing": schedule.get("pacing_json") or schedule.get("pacing"),
        "run_headless": resolve_schedule_run_headless(schedule),
        "enabled": True,
    }





async def migrate_legacy_subscription_tasks() -> int:

    """把旧版 seller_subscription 任务里的卖家迁移到独立订阅表。"""

    repo = create_task_repository()

    tasks = await repo.find_all()

    migrated = 0

    for task in tasks:

        if task.task_type != TASK_TYPE_SELLER_SUBSCRIPTION:

            continue

        seller_ids = parse_seller_user_ids(task.seller_user_ids, task.seller_urls)

        for seller_id in seller_ids:

            await add_subscription(

                seller_user_id=seller_id,

                seller_url=None,

                note=f"从任务「{task.task_name}」迁移",

            )

            migrated += 1

    return migrated



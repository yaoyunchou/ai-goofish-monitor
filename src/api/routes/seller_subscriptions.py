"""卖家订阅 API（独立于任务管理）。"""

from fastapi import APIRouter, Depends, HTTPException, Query



from src.api.dependencies import get_process_service, get_scheduler_service

from src.domain.seller_subscription import (

    SELLER_SUBSCRIPTION_TASK_NAME,

    SellerSubscriptionCreate,

    SellerSubscriptionScheduleUpdate,

    SellerSubscriptionUpdate,

)

from src.services.process_service import ProcessService

from src.services.scheduler_service import SchedulerService

from src.services.seller_subscription_service import (

    create_subscription,

    list_subscription_overview,

    patch_schedule,

    patch_subscription,

    remove_subscription,

)

from src.services.seller_subscription_storage import (

    get_schedule,

    list_item_metrics,

    list_latest_item_metrics,

    list_latest_profiles,

)



router = APIRouter(prefix="/api/seller-subscriptions", tags=["seller-subscriptions"])





async def _reload_subscription_scheduler(scheduler_service: SchedulerService) -> None:

    schedule = await get_schedule()

    await scheduler_service.reload_seller_subscription_job(schedule)





@router.get("")

async def list_seller_subscriptions():

    try:

        return await list_subscription_overview()

    except Exception as exc:

        raise HTTPException(status_code=500, detail=str(exc))





@router.post("")

async def add_seller_subscription(payload: SellerSubscriptionCreate):

    try:

        item = await create_subscription(payload)

        return {"message": "订阅添加成功", "item": item}

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc))

    except Exception as exc:

        raise HTTPException(status_code=500, detail=str(exc))





@router.patch("/schedule")

async def update_schedule(

    payload: SellerSubscriptionScheduleUpdate,

    scheduler_service: SchedulerService = Depends(get_scheduler_service),

):

    try:

        schedule = await patch_schedule(payload)

        await _reload_subscription_scheduler(scheduler_service)

        return {"message": "调度配置已更新", "schedule": schedule}

    except Exception as exc:

        raise HTTPException(status_code=500, detail=str(exc))





@router.post("/run")

async def run_seller_subscriptions(

    process_service: ProcessService = Depends(get_process_service),

):

    if process_service.is_seller_subscription_running():

        raise HTTPException(status_code=400, detail="卖家订阅采集已在运行中")

    started = await process_service.start_seller_subscription_job()

    if not started:

        raise HTTPException(status_code=500, detail="启动卖家订阅采集失败")

    return {"message": "已启动卖家订阅采集"}





@router.patch("/{subscription_id}")

async def update_seller_subscription(subscription_id: int, payload: SellerSubscriptionUpdate):

    try:

        item = await patch_subscription(subscription_id, payload)

        return {"message": "订阅已更新", "item": item}

    except ValueError as exc:

        raise HTTPException(status_code=404, detail=str(exc))

    except Exception as exc:

        raise HTTPException(status_code=500, detail=str(exc))





@router.delete("/{subscription_id}")

async def delete_seller_subscription(subscription_id: int):

    try:

        await remove_subscription(subscription_id)

        return {"message": "订阅已删除"}

    except ValueError as exc:

        raise HTTPException(status_code=404, detail=str(exc))

    except Exception as exc:

        raise HTTPException(status_code=500, detail=str(exc))





@router.get("/profiles")

async def get_profiles():

    try:

        return {

            "items": await list_latest_profiles(SELLER_SUBSCRIPTION_TASK_NAME),

        }

    except Exception as exc:

        raise HTTPException(status_code=500, detail=str(exc))





@router.get("/items")

async def get_items(

    seller_id: str | None = None,

    page_size: int = Query(100, ge=1, le=500),

):

    items = await list_latest_item_metrics(

        SELLER_SUBSCRIPTION_TASK_NAME,

        seller_user_id=seller_id,

        limit=page_size,

    )

    return {"items": items, "total": len(items)}





@router.get("/metrics")

async def get_metrics(item_id: str | None = None, limit: int = Query(200, ge=1, le=1000)):

    return {

        "items": await list_item_metrics(

            SELLER_SUBSCRIPTION_TASK_NAME,

            item_id,

            limit,

        )

    }





@router.get("/stats")

async def get_stats():

    profiles = await list_latest_profiles(SELLER_SUBSCRIPTION_TASK_NAME)

    items = await list_latest_item_metrics(SELLER_SUBSCRIPTION_TASK_NAME, limit=10000)

    schedule = await get_schedule()

    return {

        "task_name": SELLER_SUBSCRIPTION_TASK_NAME,

        "item_count": len(items),

        "seller_count": len(profiles),

        "schedule": schedule,

    }



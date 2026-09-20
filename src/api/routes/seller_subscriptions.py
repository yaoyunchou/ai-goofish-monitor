"""卖家订阅 API（独立于任务管理）。"""

from fastapi import APIRouter, Depends, HTTPException, Query



from src.api.dependencies import get_process_service, get_scheduler_service

from src.domain.seller_subscription import (

    SELLER_SUBSCRIPTION_TASK_NAME,

    SellerSubscriptionCreate,

    SellerSubscriptionScheduleUpdate,

    SellerSubscriptionUpdate,

    enrich_schedule,

    is_seller_subscription_console_log_enabled,

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

    count_latest_item_metrics,

    get_latest_profile,

    get_schedule,

    get_subscription_by_user,

    get_subscription_item_detail,

    list_item_metrics,

    list_latest_item_metrics,

    list_latest_item_metrics_paginated,

    list_latest_profiles,

    list_subscriptions,

    set_subscription_running,

)

from src.services.task_payloads import serialize_timestamp

from src.services.item_monitor_health_service import (

    MonitorConfig,

    list_health_decisions_sync,

    latest_week_sync,

    run_weekly_check,

)

from src.services.seller_item_daily_storage import unmute_item



router = APIRouter(prefix="/api/seller-subscriptions", tags=["seller-subscriptions"])





async def _reload_subscription_scheduler(scheduler_service: SchedulerService) -> None:

    schedule = await get_schedule()

    await scheduler_service.reload_seller_subscription_job(schedule)



def _attach_schedule_next_run(schedule: dict, scheduler_service: SchedulerService) -> dict:

    payload = dict(schedule)

    payload["next_run_at"] = serialize_timestamp(

        scheduler_service.get_seller_subscription_next_run_time()

    )

    return payload





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

        schedule = _attach_schedule_next_run(schedule, scheduler_service)

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

        result = await remove_subscription(subscription_id)

    except ValueError as exc:

        raise HTTPException(status_code=404, detail=str(exc))

    except Exception as exc:

        raise HTTPException(status_code=500, detail=str(exc))



    deleted = result.get("deleted") or {}

    item_count = int(deleted.get("seller_subscription_items") or 0)

    return {

        "message": f"订阅已删除，同步清理 {item_count} 个商品",

        "deleted": deleted,

    }





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

    page: int = Query(1, ge=1),

    page_size: int = Query(20, ge=1, le=100),

    search: str | None = None,

    sort_by: str = Query("snapshot_time", pattern="^(snapshot_time|price|want_count|view_count)$"),

    sort_order: str = Query("desc", pattern="^(asc|desc)$"),

):

    items = await list_latest_item_metrics_paginated(

        SELLER_SUBSCRIPTION_TASK_NAME,

        seller_user_id=seller_id,

        search=search,

        page=page,

        page_size=page_size,

        sort_by=sort_by,

        sort_order=sort_order,

    )

    total = await count_latest_item_metrics(

        SELLER_SUBSCRIPTION_TASK_NAME,

        seller_user_id=seller_id,

        search=search,

    )

    return {"items": items, "total": total, "page": page, "page_size": page_size}





@router.get("/items/health")

async def get_item_health(

    week_start: str | None = Query(None, description="判定周起始日 YYYY-MM-DD（周一）"),

    action: str | None = Query(None, description="按动作过滤：kept|muted|dry_run|skipped|interrupted"),

    limit: int = Query(200, ge=1, le=2000),

    scheduler_service: SchedulerService = Depends(get_scheduler_service),

):

    """商品监控健康度周判定结果。不传 week_start 时返回最近一次判定的周。

    注意：本路由必须声明在 `/items/{item_id}/detail` 之前，

    否则 "health" 会被当作 item_id 匹配掉。
    """

    from datetime import date as _date

    parsed: _date | None = None

    if week_start:

        try:

            parsed = _date.fromisoformat(week_start.strip())

        except ValueError:

            raise HTTPException(status_code=400, detail="week_start 格式应为 YYYY-MM-DD")

    else:

        parsed = latest_week_sync()

    rows = list_health_decisions_sync(week_start=parsed, action=action, limit=limit)

    counts: dict[str, int] = {}

    for row in rows:

        key = str(row.get("action") or "unknown")

        counts[key] = counts.get(key, 0) + 1

    return {

        "week_start": parsed.isoformat() if parsed else None,

        "counts": counts,

        "total": len(rows),

        "config": MonitorConfig.from_env().__dict__,

        "next_run_at": serialize_timestamp(scheduler_service.get_monitor_health_next_run_time()),

        "items": rows,

    }


@router.get("/items/{item_id}/detail")

async def get_item_detail(item_id: str):

    try:

        detail = await get_subscription_item_detail(SELLER_SUBSCRIPTION_TASK_NAME, item_id)

        if not detail.get("metrics") and not detail.get("record") and not detail.get("detail_api"):

            raise HTTPException(status_code=404, detail="商品不存在或尚未采集详情")

        return detail

    except HTTPException:

        raise

    except Exception as exc:

        raise HTTPException(status_code=500, detail=str(exc))





@router.get("/detail/{seller_user_id}")

async def get_seller_detail(seller_user_id: str):

    try:

        subscription = await get_subscription_by_user(seller_user_id)

        if not subscription:

            raise HTTPException(status_code=404, detail="卖家订阅不存在")

        profile = await get_latest_profile(SELLER_SUBSCRIPTION_TASK_NAME, seller_user_id)

        return {"subscription": subscription, "profile": profile}

    except HTTPException:

        raise

    except Exception as exc:

        raise HTTPException(status_code=500, detail=str(exc))




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

async def get_stats(
    process_service: ProcessService = Depends(get_process_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):

    subscriptions = await list_subscriptions()

    items = await list_latest_item_metrics(SELLER_SUBSCRIPTION_TASK_NAME, limit=10000)

    schedule = enrich_schedule(await get_schedule())
    actually_running = process_service.is_seller_subscription_running()
    db_running = bool(schedule.get("is_running"))
    if actually_running:
        schedule["is_running"] = True
        if not db_running:
            await set_subscription_running(True)
    else:
        schedule["is_running"] = False
        if db_running:
            await set_subscription_running(False)

    schedule = _attach_schedule_next_run(schedule, scheduler_service)
    next_run_at = schedule.get("next_run_at")

    return {

        "task_name": SELLER_SUBSCRIPTION_TASK_NAME,

        "item_count": len(items),

        "seller_count": len(subscriptions),

        "enabled_seller_count": sum(1 for row in subscriptions if row.get("enabled")),

        "console_log_enabled": is_seller_subscription_console_log_enabled(),

        "next_run_at": next_run_at,

        "schedule": schedule,

    }


@router.post("/items/health/run")

async def run_item_health_check(

    week_start: str | None = Query(None, description="判定周起始日 YYYY-MM-DD"),

    week_end: str | None = Query(None, description="判定周结束日 YYYY-MM-DD"),

    dry_run: bool | None = Query(None, description="覆盖 MONITOR_DRY_RUN，仅本次生效"),

    notify: bool = Query(True, description="是否推送通知"),

):

    """手动触发一次商品监控健康度判定。默认沿用环境变量的影子模式设置。"""

    from datetime import date as _date

    def _parse(value: str | None, label: str) -> _date | None:

        if not value:

            return None

        try:

            return _date.fromisoformat(value.strip())

        except ValueError:

            raise HTTPException(status_code=400, detail=f"{label} 格式应为 YYYY-MM-DD")

    summary = await run_weekly_check(

        week_start=_parse(week_start, "week_start"),

        week_end=_parse(week_end, "week_end"),

        dry_run=dry_run,

        notify=notify,

    )

    return {"message": "监控健康度判定已完成", "summary": summary}


@router.post("/items/{item_id}/restore")

async def restore_item_monitoring(

    item_id: str,

    seller_user_id: str = Query(..., description="商品所属卖家的 seller_user_id"),

):

    """恢复单个商品的监控（清除自动停用标记）。"""

    restored = await unmute_item(seller_user_id, item_id)

    if not restored:

        raise HTTPException(status_code=404, detail="未找到该商品记录，无法恢复监控")

    return {"message": f"商品 {item_id} 已恢复监控"}



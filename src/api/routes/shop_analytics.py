"""店铺数据罗盘 API。"""
from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_process_service, get_task_service
from src.services.process_service import ProcessService
from src.services.shop_datacompass_storage import list_latest_by_cycle, list_metric_trend
from src.services.task_service import TaskService

router = APIRouter(prefix="/api/shop-analytics", tags=["shop-analytics"])


def _empty_message(cycle: str) -> str:
    return f"暂无 {cycle} 周期的店铺数据快照，请先创建并运行「店铺数据罗盘」采集任务"


def _merge_overview(rows: list[dict]) -> dict:
    metrics: dict = {}
    distribution = None
    shop_name = None
    snapshot_date = None
    captured_at = None
    for row in rows:
        shop_name = row.get("shop_name") or shop_name
        snapshot_date = row.get("snapshot_date") or snapshot_date
        captured_at = row.get("captured_at") or captured_at
        parsed = row.get("metrics") or {}
        if parsed.get("metrics"):
            metrics.update(parsed["metrics"])
        if parsed.get("distribution"):
            distribution = parsed["distribution"]
    return {
        "shop_name": shop_name,
        "snapshot_date": snapshot_date,
        "captured_at": captured_at,
        "metrics": metrics,
        "distribution": distribution or {},
    }


@router.get("/overview")
async def get_overview(cycle: str = Query("1d")):
    rows = await list_latest_by_cycle(cycle)
    if not rows:
        return {
            "cycle": cycle,
            "has_data": False,
            "empty_message": _empty_message(cycle),
            "shop_name": None,
            "snapshot_date": None,
            "captured_at": None,
            "metrics": {},
            "distribution": {},
            "raw": [],
        }
    return {"cycle": cycle, "has_data": True, **_merge_overview(rows), "raw": rows}


@router.get("/flow")
async def get_flow(cycle: str = Query("1d")):
    rows = await list_latest_by_cycle(cycle)
    flow = next((row for row in rows if row.get("api_name") == "flow.detail"), None)
    return {"cycle": cycle, "flow": (flow or {}).get("metrics") or {}}


@router.get("/distribution")
async def get_distribution(cycle: str = Query("1d"), type: str = Query("source")):
    rows = await list_latest_by_cycle(cycle)
    mapping = {
        "source": "source",
        "category": "category",
        "time": "time",
        "region": "region",
    }
    key = mapping.get(type, "source")
    if not rows:
        return {
            "cycle": cycle,
            "type": key,
            "has_data": False,
            "empty_message": _empty_message(cycle),
            "items": [],
        }
    browse = next((row for row in rows if row.get("api_name") == "browse.summary"), None)
    dist = ((browse or {}).get("metrics") or {}).get("distribution") or {}
    return {"cycle": cycle, "type": key, "has_data": True, "items": dist.get(key) or []}


@router.get("/trend")
async def get_trend(
    metric: str = Query("showPv"),
    days: int = Query(30, ge=1, le=180),
    cycle: str = Query("1d"),
):
    rows = await list_latest_by_cycle(cycle)
    if not rows:
        return {
            "metric": metric,
            "cycle": cycle,
            "has_data": False,
            "empty_message": _empty_message(cycle),
            "points": [],
        }
    return {
        "metric": metric,
        "cycle": cycle,
        "has_data": True,
        "points": await list_metric_trend(metric, days, cycle),
    }


@router.post("/collect")
async def collect_now(
    task_service: TaskService = Depends(get_task_service),
    process_service: ProcessService = Depends(get_process_service),
):
    tasks = await task_service.get_all_tasks()
    target = next((task for task in tasks if task.task_type == "shop_datacompass" and task.enabled), None)
    if not target or target.id is None:
        raise HTTPException(status_code=404, detail="未找到已启用的店铺数据罗盘任务")
    if target.is_running:
        raise HTTPException(status_code=400, detail="采集任务已在运行中")
    success = await process_service.start_task(target.id, target.task_name)
    if not success:
        raise HTTPException(status_code=500, detail="启动采集失败")
    return {"message": f"已启动任务 {target.task_name}", "task_id": target.id}

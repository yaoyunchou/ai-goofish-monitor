"""小红书公开商品监控 API。采集不使用小红书登录态。"""
from __future__ import annotations

from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.api.dependencies import get_scheduler_service
from src.core.cron_utils import build_cron_trigger
from src.domain.xhs_import import build_import_template
from src.services import xhs_storage
from src.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/api/xhs", tags=["xhs"])

_COVER_HOSTS = ("xhscdn.com", "xiaohongshu.com")


class ProductCreate(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    shop_name: str | None = None
    category: str | None = None
    tags: list[str] | None = None


class ProductLabelsUpdate(BaseModel):
    shop_name: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)


class ShopCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class FailureIgnore(BaseModel):
    product_ids: list[str] = Field(min_length=1, max_length=200)


class ScheduleUpdate(BaseModel):
    cron: str = Field(min_length=1, max_length=80)
    enabled: bool = False


def _json_row(row: dict) -> dict:
    payload = dict(row)
    for key, value in payload.items():
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
        elif isinstance(value, dict):
            payload[key] = _json_row(value)
        elif isinstance(value, list):
            payload[key] = [_json_row(item) if isinstance(item, dict) else item for item in value]
    return payload


@router.get("/products")
async def list_products():
    rows = xhs_storage.list_board()
    return {"items": [_json_row(row) for row in rows]}


@router.get("/failures")
async def list_failures():
    rows = xhs_storage.list_products_by_status(("failed", "skipped"))
    return {"items": [_json_row(row) for row in rows]}


@router.post("/failures/ignore")
async def ignore_failures(body: FailureIgnore):
    updated = xhs_storage.ignore_failures(body.product_ids)
    return {"updated": updated}


@router.get("/delisted")
async def list_delisted():
    rows = xhs_storage.list_products_by_status(("delisted",))
    return {"items": [_json_row(row) for row in rows]}


@router.post("/products")
async def create_product(body: ProductCreate):
    try:
        row = xhs_storage.add_product(
            body.url,
            shop_name=body.shop_name,
            category=body.category,
            tags=body.tags,
        )
    except xhs_storage.ShortLinkBlocked as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _json_row(row)


@router.get("/products/import-template")
async def import_template():
    return Response(
        content=build_import_template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="xhs-products-template.xlsx"'},
    )


@router.post("/products/import")
async def import_products(file: UploadFile = File(...)):
    name = (file.filename or "").lower()
    if not name.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="请上传 .xlsx 文件")
    payload = await file.read()
    if len(payload) > 2_000_000:
        raise HTTPException(status_code=400, detail="文件过大")
    try:
        return xhs_storage.import_product_rows(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/shops")
async def list_shops():
    payload = xhs_storage.list_shops()
    return {
        "items": [_json_row(row) for row in payload["items"]],
        "unassigned": _json_row(payload["unassigned"]),
    }


@router.post("/shops")
async def create_shop(body: ShopCreate):
    try:
        return xhs_storage.create_shop(body.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/shops/{shop_id}")
async def shop_detail(shop_id: int):
    try:
        payload = xhs_storage.get_shop(shop_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="店铺不存在") from None
    return _json_row(payload)


@router.patch("/products/{product_id}")
async def update_product_labels(product_id: str, body: ProductLabelsUpdate):
    try:
        row = xhs_storage.update_labels(
            product_id,
            shop_name=body.shop_name,
            category=body.category,
            tags=body.tags,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="商品不在监控列表") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _json_row(row)


@router.delete("/products/{product_id}")
async def remove_product(product_id: str):
    xhs_storage.deactivate_product(product_id)
    return {"ok": True}


@router.post("/products/{product_id}/collect")
async def collect_product(product_id: str):
    try:
        xhs_storage.get_product(product_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="商品不在监控列表") from None
    return xhs_storage.collect_one(product_id)


@router.post("/collect")
async def collect_all():
    return xhs_storage.collect_products()


@router.get("/products/{product_id}")
async def product_detail(product_id: str):
    try:
        product = xhs_storage.get_product(product_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="商品不在监控列表") from None
    board = next((row for row in xhs_storage.list_board() if row["id"] == product_id), None)
    return _json_row(board or product)


@router.get("/products/{product_id}/series")
async def product_series(product_id: str, kind: str = Query(default="hourly")):
    if kind not in {"hourly", "daily"}:
        raise HTTPException(status_code=400, detail="kind 只能是 hourly 或 daily")
    try:
        xhs_storage.get_product(product_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="商品不在监控列表") from None
    return {"kind": kind, "points": xhs_storage.product_series(product_id, kind)}


@router.get("/schedule")
async def read_schedule(scheduler: SchedulerService = Depends(get_scheduler_service)):
    schedule = xhs_storage.get_schedule()
    next_run = scheduler.get_xhs_next_run_time()
    return {
        **schedule,
        "next_run_at": next_run.isoformat() if next_run else None,
    }


@router.patch("/schedule")
async def update_schedule(
    body: ScheduleUpdate,
    scheduler: SchedulerService = Depends(get_scheduler_service),
):
    try:
        build_cron_trigger(body.cron, timezone="Asia/Shanghai")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    saved = xhs_storage.save_schedule(body.cron, body.enabled)
    await scheduler.reload_xhs_job(saved)
    next_run = scheduler.get_xhs_next_run_time()
    return {**saved, "next_run_at": next_run.isoformat() if next_run else None}


def _cover_allowed(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(
        host == domain or host.endswith("." + domain) for domain in _COVER_HOSTS
    )


@router.get("/cover")
async def cover_proxy(url: str = Query(min_length=8)):
    if not _cover_allowed(url):
        raise HTTPException(status_code=400, detail="只代理小红书图床")
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=15) as response:
            final = urlparse(response.geturl())
            host = (final.hostname or "").lower()
            if not any(host == domain or host.endswith("." + domain) for domain in _COVER_HOSTS):
                raise HTTPException(status_code=400, detail="图床跳转到了不允许的地址")
            content_type = response.headers.get("Content-Type", "image/jpeg")
            body = response.read(2_000_000)
    except HTTPException:
        raise
    except (HTTPError, URLError) as exc:
        raise HTTPException(status_code=502, detail="主图拉取失败") from exc
    return Response(content=body, media_type=content_type.split(";")[0])

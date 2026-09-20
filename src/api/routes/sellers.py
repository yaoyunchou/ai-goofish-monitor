"""关注卖家 API"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.services import seller_service

router = APIRouter(prefix="/api/sellers", tags=["sellers"])


class FollowRequest(BaseModel):
    seller_id: str
    seller_name: str = ""
    avatar_url: str = ""
    city: str = ""
    cron: str = "0 */6 * * *"
    note: str = ""


class CronUpdate(BaseModel):
    cron: str


@router.get("")
async def list_sellers():
    return {"items": seller_service.list_followed_sellers()}


@router.post("")
async def follow_seller_api(body: FollowRequest):
    return seller_service.follow_seller(
        body.seller_id,
        seller_name=body.seller_name,
        avatar_url=body.avatar_url,
        city=body.city,
        cron=body.cron,
        note=body.note,
    )


@router.delete("/{seller_id}")
async def unfollow_seller_api(seller_id: str):
    if not seller_service.unfollow_seller(seller_id):
        raise HTTPException(status_code=404, detail="未关注该卖家")
    return {"message": "已取消关注"}


@router.get("/{seller_id}")
async def get_seller_api(seller_id: str, sort: str = Query("want_cnt")):
    seller = seller_service.get_followed_seller(seller_id)
    if not seller:
        raise HTTPException(status_code=404, detail="未关注该卖家")
    items = seller_service.get_seller_items(seller_id, sort_by=sort)
    return {"seller": seller, "items": items}


@router.post("/{seller_id}/refresh")
async def refresh_seller_api(seller_id: str):
    return await seller_service.refresh_seller_items(seller_id)


@router.post("/refresh-all")
async def refresh_all_sellers_api():
    return {"results": await seller_service.refresh_all_sellers()}


@router.put("/{seller_id}/cron")
async def update_cron_api(seller_id: str, body: CronUpdate):
    if not seller_service.update_seller_cron(seller_id, body.cron):
        raise HTTPException(status_code=404, detail="未关注该卖家")
    return {"message": "cron 已更新", "cron": body.cron}

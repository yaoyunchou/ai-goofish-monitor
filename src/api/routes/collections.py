"""
收录商品 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.services import collection_service


router = APIRouter(prefix="/api/collections", tags=["collections"])


class CollectRequest(BaseModel):
    result_item_id: int | None = None
    result_filename: str | None = None
    item_id: str | None = Field(default=None, description="闲鱼商品 ID")


@router.get("")
async def list_collections():
    return {"items": await collection_service.list_collections()}


@router.get("/lookup")
async def lookup_collection(result_filename: str, item_id: str):
    row_id = collection_service.lookup_result_item_id(result_filename, item_id)
    if row_id is None:
        raise HTTPException(status_code=404, detail="结果商品未找到")
    existing = await collection_service.list_collections()
    for item in existing:
        if item.get("result_item_id") == row_id:
            return {"collected": True, "collection_id": item["id"]}
    return {"collected": False, "result_item_id": row_id}


@router.post("")
async def collect_item(body: CollectRequest):
    try:
        item = await collection_service.collect_result_item(
            result_item_id=body.result_item_id,
            result_filename=body.result_filename,
            item_id=body.item_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "收录成功", "collection": item}


@router.get("/{collection_id}")
async def get_collection(collection_id: int):
    item = await collection_service.get_collection(collection_id)
    if not item:
        raise HTTPException(status_code=404, detail="收录记录未找到")
    return item


@router.post("/{collection_id}/refresh-skus")
async def refresh_skus(collection_id: int):
    try:
        item = await collection_service.refresh_collection_skus(collection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "SKU 已刷新", "collection": item}


@router.delete("/{collection_id}")
async def remove_collection(collection_id: int):
    deleted = await collection_service.delete_collection(collection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="收录记录未找到")
    return {"message": "已取消收录"}

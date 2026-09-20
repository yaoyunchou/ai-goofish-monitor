"""
闲鱼账号管理路由（DB 优先，兼容文件）
"""
import json
import os
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

from src.services.account_state_store import (
    list_account_names,
    get_account_state,
    save_account_state,
    delete_account_state,
)


router = APIRouter(prefix="/api/accounts", tags=["accounts"])

ACCOUNT_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,50}$")


class AccountCreate(BaseModel):
    name: str
    content: str


class AccountUpdate(BaseModel):
    content: str


def _validate_name(name: str) -> str:
    trimmed = name.strip()
    if not trimmed or not ACCOUNT_NAME_RE.match(trimmed):
        raise HTTPException(status_code=400, detail="账号名称只能包含字母、数字、下划线或短横线。")
    return trimmed


def _validate_json(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="提供的内容不是有效的JSON格式。")


@router.get("", response_model=List[dict])
async def list_accounts():
    names = list_account_names()
    return [{"name": n, "path": f"state/{n}.json"} for n in names]


@router.get("/{name}", response_model=dict)
async def get_account(name: str):
    account_name = _validate_name(name)
    state = get_account_state(account_name)
    if state is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    return {"name": account_name, "path": f"state/{account_name}.json", "content": json.dumps(state, ensure_ascii=False)}


@router.post("", response_model=dict)
async def create_account(data: AccountCreate):
    account_name = _validate_name(data.name)
    content = _validate_json(data.content)
    existing = get_account_state(account_name)
    if existing is not None:
        raise HTTPException(status_code=409, detail="账号已存在")
    save_account_state(account_name, content)
    return {"message": "账号已添加", "name": account_name, "path": f"state/{account_name}.json"}


@router.put("/{name}", response_model=dict)
async def update_account(name: str, data: AccountUpdate):
    account_name = _validate_name(name)
    content = _validate_json(data.content)
    existing = get_account_state(account_name)
    if existing is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    save_account_state(account_name, content)
    return {"message": "账号已更新", "name": account_name, "path": f"state/{account_name}.json"}


@router.delete("/{name}", response_model=dict)
async def delete_account(name: str):
    account_name = _validate_name(name)
    deleted = delete_account_state(account_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="账号不存在")
    return {"message": "账号已删除"}

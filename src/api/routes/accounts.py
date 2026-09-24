"""账号管理。闲鱼文件在 state/ 根目录，小红书文件在 state/xhs/。"""
import json
import os

import aiofiles
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional

from src.infrastructure.config.env_manager import env_manager
from src.services.monitor_accounts import (
    ACCOUNT_NAME_RE,
    delete_account_row,
    get_account,
    list_accounts,
    sync_goofish_files,
    upsert_account,
)


router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountCreate(BaseModel):
    name: str
    content: str
    channel: str = "goofish"
    enabled: bool = True


class AccountUpdate(BaseModel):
    content: str
    channel: str = "goofish"
    enabled: Optional[bool] = None


def _strip_quotes(value: str) -> str:
    if not value:
        return value
    if value.startswith(("\"", "'")) and value.endswith(("\"", "'")):
        return value[1:-1]
    return value


def _state_dir() -> str:
    raw = env_manager.get_value("ACCOUNT_STATE_DIR", "state") or "state"
    return _strip_quotes(raw.strip())


def _validate_name(name: str) -> str:
    trimmed = name.strip()
    if not trimmed or not ACCOUNT_NAME_RE.match(trimmed):
        raise HTTPException(status_code=400, detail="账号名称只能包含字母、数字、下划线或短横线。")
    return trimmed


def _validate_channel(channel: str) -> str:
    value = (channel or "goofish").strip()
    if value not in ("goofish", "xhs"):
        raise HTTPException(status_code=400, detail="渠道只能是闲鱼或小红书")
    return value


def _validate_json(content: str) -> None:
    try:
        json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="提供的内容不是有效的JSON格式。")


def _relative_path(channel: str, name: str) -> str:
    if channel == "xhs":
        return f"xhs/{name}.json"
    return f"{name}.json"


def _absolute_path(state_path: str) -> str:
    return os.path.join(_state_dir(), state_path.replace("/", os.sep))


def _payload(row: dict, content: str | None = None) -> dict:
    body = {
        "id": row["id"],
        "name": row["name"],
        "channel": row["channel"],
        "path": _absolute_path(row["state_path"]),
        "state_path": row["state_path"],
        "enabled": row["enabled"],
        "last_checked_at": row["last_checked_at"],
        "last_error": row["last_error"],
    }
    if content is not None:
        body["content"] = content
    return body


@router.get("", response_model=List[dict])
async def list_account_files(channel: Optional[str] = Query(default=None)):
    selected = _validate_channel(channel) if channel else None
    sync_goofish_files(_state_dir())
    rows = list_accounts(selected)
    return [_payload(row) for row in rows]


@router.get("/{name}", response_model=dict)
async def get_account_file(name: str, channel: str = Query(default="goofish")):
    account_name = _validate_name(name)
    selected = _validate_channel(channel)
    row = get_account(selected, account_name)
    path = _absolute_path(row["state_path"]) if row else _absolute_path(_relative_path(selected, account_name))
    if row is None or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="账号不存在")
    async with aiofiles.open(path, "r", encoding="utf-8") as handle:
        content = await handle.read()
    return _payload(row, content)


@router.post("", response_model=dict)
async def create_account(data: AccountCreate):
    account_name = _validate_name(data.name)
    selected = _validate_channel(data.channel)
    _validate_json(data.content)
    relative = _relative_path(selected, account_name)
    path = _absolute_path(relative)
    if os.path.exists(path) or get_account(selected, account_name):
        raise HTTPException(status_code=409, detail="账号已存在")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as handle:
        await handle.write(data.content)
    row = upsert_account(selected, account_name, relative, enabled=data.enabled)
    return {"message": "账号已添加", **_payload(row)}


@router.put("/{name}", response_model=dict)
async def update_account(name: str, data: AccountUpdate):
    account_name = _validate_name(name)
    selected = _validate_channel(data.channel)
    _validate_json(data.content)
    row = get_account(selected, account_name)
    if row is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    path = _absolute_path(row["state_path"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as handle:
        await handle.write(data.content)
    enabled = row["enabled"] if data.enabled is None else data.enabled
    saved = upsert_account(selected, account_name, row["state_path"], enabled=enabled)
    return {"message": "账号已更新", **_payload(saved)}


@router.delete("/{name}", response_model=dict)
async def delete_account(name: str, channel: str = Query(default="goofish")):
    account_name = _validate_name(name)
    selected = _validate_channel(channel)
    row = get_account(selected, account_name)
    path = _absolute_path(row["state_path"]) if row else _absolute_path(_relative_path(selected, account_name))
    if row is None and not os.path.exists(path):
        raise HTTPException(status_code=404, detail="账号不存在")
    if os.path.exists(path):
        os.remove(path)
    if row is not None:
        delete_account_row(selected, account_name)
    return {"message": "账号已删除"}

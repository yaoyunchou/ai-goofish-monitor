"""小红书笔记。采集使用小红书登录态，和商品公开页分开。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import get_scheduler_service
from src.core.cron_utils import build_cron_trigger
from src.services import xhs_note_storage
from src.services.channel_workers import ChannelBusy, get_channel_workers
from src.services.monitor_accounts import list_accounts
from src.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/api/xhs/notes", tags=["xhs-notes"])


class NoteCreate(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    account_id: int | None = None


class NoteScheduleUpdate(BaseModel):
    cron: str
    enabled: bool
    account_id: int | None = None


def _json_row(row: dict) -> dict:
    body = dict(row)
    for key, value in list(body.items()):
        if hasattr(value, "isoformat"):
            body[key] = value.isoformat()
    return body


async def _collect(work):
    try:
        _status, done = get_channel_workers().submit(
            "xhs_note", work, wait=False, on_thread=True
        )
    except ChannelBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return await asyncio.wrap_future(done)


@router.get("")
async def list_notes():
    return {"items": [_json_row(row) for row in xhs_note_storage.list_notes()]}


@router.post("")
async def create_note(body: NoteCreate):
    try:
        row = xhs_note_storage.add_note(body.url, account_id=body.account_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _json_row(row)


@router.delete("/{note_id}")
async def remove_note(note_id: str):
    xhs_note_storage.deactivate_note(note_id)
    return {"ok": True}


@router.post("/collect")
async def collect_all():
    return await _collect(xhs_note_storage.collect_notes)


@router.post("/{note_id}/collect")
async def collect_one(note_id: str):
    try:
        xhs_note_storage.get_note(note_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="笔记不在监控列表") from None
    return await _collect(lambda: xhs_note_storage.collect_notes(note_id))


@router.get("/accounts")
async def note_accounts():
    rows = [row for row in list_accounts("xhs") if row["enabled"]]
    return {"items": rows}


@router.get("/schedule")
async def read_schedule(scheduler: SchedulerService = Depends(get_scheduler_service)):
    schedule = xhs_note_storage.get_schedule()
    next_run = scheduler.get_xhs_note_next_run_time()
    return {**schedule, "next_run_at": next_run.isoformat() if next_run else None}


@router.patch("/schedule")
async def update_schedule(
    body: NoteScheduleUpdate,
    scheduler: SchedulerService = Depends(get_scheduler_service),
):
    try:
        build_cron_trigger(body.cron, timezone="Asia/Shanghai")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    saved = xhs_note_storage.save_schedule(body.cron, body.enabled, body.account_id)
    await scheduler.reload_xhs_note_job(saved)
    next_run = scheduler.get_xhs_note_next_run_time()
    return {**saved, "next_run_at": next_run.isoformat() if next_run else None}

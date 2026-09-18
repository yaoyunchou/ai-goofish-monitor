"""卖家订阅领域常量与模型。"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.config import RUN_HEADLESS, SELLER_SUBSCRIPTION_CONSOLE_LOG
from src.domain.seller_ids import DEFAULT_SELLER_SUBSCRIPTION_ITEM_LIMIT, parse_seller_user_ids


def resolve_schedule_run_headless(schedule: dict[str, Any]) -> bool:
    """调度未显式配置 run_headless 时继承全局 RUN_HEADLESS。"""
    raw = schedule.get("run_headless")
    if raw is None:
        return RUN_HEADLESS
    return bool(raw)


def enrich_schedule(schedule: dict[str, Any]) -> dict[str, Any]:
    payload = dict(schedule)
    payload["run_headless_effective"] = resolve_schedule_run_headless(schedule)
    return payload


def is_seller_subscription_console_log_enabled() -> bool:
    """是否在采集控制台内嵌展示卖家订阅实时日志（见 .env SELLER_SUBSCRIPTION_CONSOLE_LOG）。"""
    return SELLER_SUBSCRIPTION_CONSOLE_LOG

SELLER_SUBSCRIPTION_TASK_NAME = "seller_subscriptions"
SELLER_SUBSCRIPTION_JOB_ID = -1
DEFAULT_SELLER_SUBSCRIPTION_CRON = "0 8 * * *"


class SellerSubscriptionCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    seller_url: str = ""
    seller_user_id: str = ""
    note: Optional[str] = ""

    def resolved_user_id(self) -> str | None:
        values = parse_seller_user_ids(self.seller_user_id, self.seller_url)
        return values[0] if values else None


class SellerSubscriptionUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: Optional[bool] = None
    note: Optional[str] = None


class SellerSubscriptionScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: Optional[bool] = None
    cron: Optional[str] = None
    item_limit: Optional[int] = Field(default=None, ge=1, le=500)
    collect_ratings: Optional[bool] = None
    account_state_file: Optional[str] = None
    account_strategy: Optional[Literal["auto", "fixed", "rotate"]] = None
    run_headless: Optional[bool] = None


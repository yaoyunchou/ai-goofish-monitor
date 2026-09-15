"""卖家订阅领域常量与模型。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.domain.seller_ids import DEFAULT_SELLER_SUBSCRIPTION_ITEM_LIMIT, parse_seller_user_ids

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

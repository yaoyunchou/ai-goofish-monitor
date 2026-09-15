"""卖家订阅详情采集的模拟访问节奏策略。"""

from __future__ import annotations



import random

from dataclasses import dataclass

from typing import Any



from src.utils import random_sleep



DEFAULT_PACING: dict[str, float | int] = {

    # 每条详情前的随机等待（秒）

    "detail_delay_min": 4.0,

    "detail_delay_max": 8.0,

    # 每批处理条数，批末额外休息

    "batch_size": 10,

    "batch_cooldown_min": 60.0,

    "batch_cooldown_max": 120.0,

    # 切换卖家前的休息（秒）

    "seller_cooldown_min": 120.0,

    "seller_cooldown_max": 300.0,

    # 打开卖家主页后的预热等待

    "profile_warmup_min": 3.0,

    "profile_warmup_max": 6.0,

    # 每 N 条详情插入一次「走神」长暂停

    "long_pause_every": 25,

    "long_pause_min": 90.0,

    "long_pause_max": 180.0,

}





@dataclass(frozen=True)

class SubscriptionPacingConfig:

    detail_delay_min: float = 4.0

    detail_delay_max: float = 8.0

    batch_size: int = 10

    batch_cooldown_min: float = 60.0

    batch_cooldown_max: float = 120.0

    seller_cooldown_min: float = 120.0

    seller_cooldown_max: float = 300.0

    profile_warmup_min: float = 3.0

    profile_warmup_max: float = 6.0

    long_pause_every: int = 25

    long_pause_min: float = 90.0

    long_pause_max: float = 180.0



    @classmethod

    def from_mapping(cls, raw: dict[str, Any] | None) -> "SubscriptionPacingConfig":

        merged = {**DEFAULT_PACING, **(raw or {})}

        return cls(

            detail_delay_min=float(merged["detail_delay_min"]),

            detail_delay_max=float(merged["detail_delay_max"]),

            batch_size=max(1, int(merged["batch_size"])),

            batch_cooldown_min=float(merged["batch_cooldown_min"]),

            batch_cooldown_max=float(merged["batch_cooldown_max"]),

            seller_cooldown_min=float(merged["seller_cooldown_min"]),

            seller_cooldown_max=float(merged["seller_cooldown_max"]),

            profile_warmup_min=float(merged["profile_warmup_min"]),

            profile_warmup_max=float(merged["profile_warmup_max"]),

            long_pause_every=max(1, int(merged["long_pause_every"])),

            long_pause_min=float(merged["long_pause_min"]),

            long_pause_max=float(merged["long_pause_max"]),

        )



    def estimate_seconds(self, seller_count: int, items_per_seller: int) -> int:

        if seller_count <= 0 or items_per_seller <= 0:

            return 0

        detail_avg = (self.detail_delay_min + self.detail_delay_max) / 2

        batch_avg = (self.batch_cooldown_min + self.batch_cooldown_max) / 2

        seller_avg = (self.seller_cooldown_min + self.seller_cooldown_max) / 2

        batches_per_seller = max(1, (items_per_seller + self.batch_size - 1) // self.batch_size)

        per_seller = (

            items_per_seller * detail_avg

            + max(0, batches_per_seller - 1) * batch_avg

            + (items_per_seller // self.long_pause_every)

            * ((self.long_pause_min + self.long_pause_max) / 2)

        )

        total = seller_count * per_seller + max(0, seller_count - 1) * seller_avg

        return int(total)





class SubscriptionPacing:

    """按批、按卖家、带随机抖动的详情采集节奏控制器。"""



    def __init__(self, config: SubscriptionPacingConfig):

        self.config = config

        self._details_in_seller = 0



    @classmethod

    def from_task_config(cls, task_config: dict) -> "SubscriptionPacing":

        raw = task_config.get("pacing") or task_config.get("pacing_json")

        return cls(SubscriptionPacingConfig.from_mapping(raw))



    def log_plan(self, seller_count: int, items_per_seller: int) -> None:

        minutes = max(1, self.config.estimate_seconds(seller_count, items_per_seller) // 60)

        print(

            f"[订阅策略] {seller_count} 个卖家 × 最多 {items_per_seller} 条/卖家；"

            f"详情间隔 {self.config.detail_delay_min}-{self.config.detail_delay_max}s，"

            f"每 {self.config.batch_size} 条批休 {self.config.batch_cooldown_min}-"

            f"{self.config.batch_cooldown_max}s，"

            f"切换卖家休 {self.config.seller_cooldown_min}-{self.config.seller_cooldown_max}s；"

            f"预计总耗时约 {minutes} 分钟（模拟浏览，非一口气打完）。"

        )



    async def before_seller(self, seller_index: int) -> None:

        self._details_in_seller = 0

        if seller_index > 0:

            print("   [策略] 切换卖家，模拟离开上一店铺…")

            await random_sleep(

                self.config.seller_cooldown_min,

                self.config.seller_cooldown_max,

            )



    async def before_profile(self) -> None:

        print("   [策略] 打开卖家主页，预热等待…")

        await random_sleep(

            self.config.profile_warmup_min,

            self.config.profile_warmup_max,

        )



    async def before_detail(self, item_index: int) -> None:

        if item_index > 0:

            await random_sleep(

                self.config.detail_delay_min,

                self.config.detail_delay_max,

            )



    async def after_detail(self, item_index: int) -> None:

        self._details_in_seller += 1

        completed = item_index + 1

        if completed % self.config.batch_size == 0:

            print(f"   [策略] 本批已处理 {completed} 条，批间休息…")

            await random_sleep(

                self.config.batch_cooldown_min,

                self.config.batch_cooldown_max,

            )

        elif completed % self.config.long_pause_every == 0:

            print(f"   [策略] 已浏览 {completed} 条，模拟停顿…")

            await random_sleep(

                self.config.long_pause_min,

                self.config.long_pause_max,

            )



    @staticmethod

    def shuffle_items(items: list[dict]) -> list[dict]:

        shuffled = list(items)

        random.shuffle(shuffled)

        return shuffled



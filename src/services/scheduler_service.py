"""
调度服务
负责管理定时任务的调度
"""
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import List

from src.core.cron_utils import build_cron_trigger
from src.domain.models.task import Task
from src.services.process_service import ProcessService


class SchedulerService:
    """调度服务"""

    def __init__(self, process_service: ProcessService):
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self.process_service = process_service

    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            print("调度器已启动")

    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("调度器已停止")

    def get_next_run_time(self, task_id: int):
        job = self.scheduler.get_job(f"task_{task_id}")
        if job is None:
            return None

        next_run_time = getattr(job, "next_run_time", None)
        if next_run_time is not None:
            return next_run_time

        trigger = getattr(job, "trigger", None)
        if trigger is None or not hasattr(trigger, "get_next_fire_time"):
            return None

        try:
            now = datetime.now(self.scheduler.timezone)
            return trigger.get_next_fire_time(None, now)
        except Exception:
            return None

    async def reload_jobs(self, tasks: List[Task]):
        """重新加载所有定时任务"""
        print("正在重新加载定时任务...")
        self.scheduler.remove_all_jobs()

        for task in tasks:
            if task.enabled and task.cron:
                try:
                    trigger = build_cron_trigger(
                        task.cron,
                        timezone=self.scheduler.timezone,
                    )
                    self.scheduler.add_job(
                        self._run_task,
                        trigger=trigger,
                        args=[task.id, task.task_name],
                        id=f"task_{task.id}",
                        name=f"Scheduled: {task.task_name}",
                        replace_existing=True
                    )
                    print(f"  -> 已为任务 '{task.task_name}' 添加定时规则: '{task.cron}'")
                except ValueError as e:
                    print(f"  -> [警告] 任务 '{task.task_name}' 的 Cron 表达式无效: {e}")

        # 加载关注卖家定时任务
        self._load_seller_jobs()

        print("定时任务加载完成")

    def _load_seller_jobs(self):
        """加载关注卖家的定时刷新任务"""
        try:
            from src.services.seller_service import list_followed_sellers
            sellers = list_followed_sellers()
            for s in sellers:
                sid = s.get("seller_id")
                cron = s.get("cron") or "0 */6 * * *"
                if not sid:
                    continue
                try:
                    trigger = build_cron_trigger(cron, timezone=self.scheduler.timezone)
                    self.scheduler.add_job(
                        self._run_seller_refresh,
                        trigger=trigger,
                        args=[sid],
                        id=f"seller_{sid}",
                        name=f"SellerRefresh: {sid}",
                        replace_existing=True,
                    )
                    print(f"  -> 已为关注卖家 '{sid}' 添加定时规则: '{cron}'")
                except ValueError as e:
                    print(f"  -> [警告] 关注卖家 '{sid}' 的 Cron 表达式无效: {e}")
        except Exception as e:
            print(f"  -> [警告] 加载关注卖家任务失败: {e}")

    async def _run_seller_refresh(self, seller_id: str):
        """执行关注卖家刷新任务"""
        from src.services.seller_service import refresh_seller_items
        print(f"关注卖家定时刷新触发: seller_id={seller_id}")
        await refresh_seller_items(seller_id)

    async def _run_task(self, task_id: int, task_name: str):
        """执行定时任务"""
        print(f"定时任务触发: 正在为任务 '{task_name}' 启动爬虫...")
        await self.process_service.start_task(task_id, task_name)

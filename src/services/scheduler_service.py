"""
调度服务
负责管理定时任务的调度
"""
import logging
import os
from datetime import datetime
from typing import List

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.cron_utils import build_cron_trigger
from src.domain.models.task import TASK_TYPE_SELLER_SUBSCRIPTION, Task
from src.infrastructure.logging_config import configure_scheduler_file_logging
from src.services.process_service import ProcessService

MONITOR_HEALTH_JOB_ID = "item_monitor_health_weekly"
DEFAULT_MONITOR_HEALTH_CRON = "0 9 * * 1"  # 每周一 09:00（Asia/Shanghai）
# APScheduler 默认 misfire_grace_time=1 秒。Windows 上 asyncio.call_later 隔夜等待
# 经常迟到数秒到数分钟，每日 Cron 会被直接判 missed、不跑采集。
# 1 小时只覆盖「进程一直在、定时器晚点」；进程 11 点才启动时 9 点那枪仍不补跑。
DAILY_JOB_MISFIRE_GRACE_SECONDS = 3600

_scheduler_log = logging.getLogger("apscheduler")


class SchedulerService:
    """调度服务"""

    def __init__(self, process_service: ProcessService):
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self.process_service = process_service
        self.scheduler.add_listener(
            self._on_job_event,
            EVENT_JOB_MISSED | EVENT_JOB_ERROR | EVENT_JOB_EXECUTED,
        )

    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            configure_scheduler_file_logging()
            self.scheduler.start()
            print("调度器已启动")

    def _cron_job_options(self) -> dict:
        return {
            "misfire_grace_time": DAILY_JOB_MISFIRE_GRACE_SECONDS,
            "coalesce": True,
            "max_instances": 1,
            "replace_existing": True,
        }

    def _on_job_event(self, event) -> None:
        job_id = getattr(event, "job_id", "?")
        scheduled = getattr(event, "scheduled_run_time", None)
        if event.code == EVENT_JOB_MISSED:
            message = f"[调度] 错过 {job_id} 计划时间 {scheduled}，未执行"
        elif event.code == EVENT_JOB_ERROR:
            message = f"[调度] {job_id} 执行失败: {getattr(event, 'exception', None)}"
        else:
            message = f"[调度] 已执行 {job_id} 计划时间 {scheduled}"
        print(message)
        _scheduler_log.info(message)

    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("调度器已停止")

    def get_next_run_time(self, task_id: int):
        return self._job_next_run_time(f"task_{task_id}")

    def get_seller_subscription_next_run_time(self):
        """读取卖家订阅 job 的下次执行时间；job 未挂上时返回 None。"""
        return self._job_next_run_time("seller_subscriptions")

    def _job_next_run_time(self, job_id: str):
        job = self.scheduler.get_job(job_id)
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

    def _remove_keyword_task_jobs(self) -> None:
        """只移除 keyword 任务 job（id 以 task_ 开头），永不碰 seller_subscriptions。"""
        for job in list(self.scheduler.get_jobs()):
            job_id = str(job.id)
            if job_id.startswith("task_"):
                self.scheduler.remove_job(job_id)

    async def reload_jobs(self, tasks: List[Task]):
        """重新加载关键词定时任务，保留卖家订阅独立 job。"""
        print("正在重新加载定时任务...")
        self._remove_keyword_task_jobs()

        for task in tasks:
            if task.task_type == TASK_TYPE_SELLER_SUBSCRIPTION:
                continue
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
                        **self._cron_job_options(),
                    )
                    print(f"  -> 已为任务 '{task.task_name}' 添加定时规则: '{task.cron}'")
                except ValueError as e:
                    print(f"  -> [警告] 任务 '{task.task_name}' 的 Cron 表达式无效: {e}")

        print("定时任务加载完成")

    async def reload_seller_subscription_job(self, schedule: dict):
        """加载卖家订阅独立定时任务。"""
        job_id = "seller_subscriptions"
        existing = self.scheduler.get_job(job_id)
        if existing is not None:
            self.scheduler.remove_job(job_id)

        if schedule.get("enabled") and schedule.get("cron"):
            try:
                trigger = build_cron_trigger(
                    schedule["cron"],
                    timezone=self.scheduler.timezone,
                )
                self.scheduler.add_job(
                    self._run_seller_subscriptions,
                    trigger=trigger,
                    id=job_id,
                    name="Scheduled: seller subscriptions",
                    **self._cron_job_options(),
                )
                print(f"  -> 已为卖家订阅添加定时规则: '{schedule['cron']}'")
            except ValueError as exc:
                print(f"  -> [警告] 卖家订阅 Cron 无效: {exc}")

    def reload_monitor_health_job(self, cron: str | None = None) -> bool:
        """加载商品监控健康度周判定 job（单例）。

        注意：这里 **不** 由 reload_jobs 调用 —— reload_jobs 只清理 `task_*`，
        本 job 与 seller_subscriptions 一样是独立单例，避免被误删。
        """
        existing = self.scheduler.get_job(MONITOR_HEALTH_JOB_ID)
        if existing is not None:
            self.scheduler.remove_job(MONITOR_HEALTH_JOB_ID)

        expression = (cron or os.getenv("MONITOR_HEALTH_CRON") or DEFAULT_MONITOR_HEALTH_CRON).strip()
        if not expression:
            return False
        try:
            trigger = build_cron_trigger(expression, timezone=self.scheduler.timezone)
        except ValueError as exc:
            print(f"  -> [警告] 监控健康度 Cron 无效（{expression}）: {exc}")
            return False

        self.scheduler.add_job(
            self._run_monitor_health_check,
            trigger=trigger,
            id=MONITOR_HEALTH_JOB_ID,
            name="Scheduled: item monitor health check",
            **self._cron_job_options(),
        )
        print(f"  -> 已为商品监控健康度添加定时规则: '{expression}'")
        return True

    def get_monitor_health_next_run_time(self):
        return self._job_next_run_time(MONITOR_HEALTH_JOB_ID)

    async def _run_task(self, task_id: int, task_name: str):
        """执行定时任务"""
        print(f"定时任务触发: 正在为任务 '{task_name}' 启动爬虫...")
        await self.process_service.start_task(task_id, task_name)

    async def _run_seller_subscriptions(self):
        print("定时任务触发: 正在启动卖家订阅采集...")
        await self.process_service.start_seller_subscription_job()

    async def _run_monitor_health_check(self):
        """执行商品监控健康度周判定（自动停用 + 通知）。"""
        from src.services.item_monitor_health_service import run_weekly_check

        print("定时任务触发: 正在执行商品监控健康度周判定...")
        try:
            summary = await run_weekly_check()
            print(
                "  监控健康度判定完成: "
                f"评估 {summary.get('evaluated', 0)} 个商品，"
                f"保留 {summary.get('kept', 0)}，"
                f"跳过 {summary.get('skipped', 0)}，"
                f"中断 {summary.get('interrupted', 0)}，"
                f"停用 {summary.get('muted', 0)}"
                f"{'（试运行）' if summary.get('dry_run') else ''}"
            )
        except Exception as exc:  # 判定失败不能影响其它调度
            print(f"  [错误] 监控健康度判定失败: {exc}")

"""SchedulerService 单元测试（阶段三：卖家订阅定时任务）。"""
import asyncio
from datetime import datetime

from src.domain.models.task import Task
from src.services.process_service import ProcessService
from src.services.scheduler_service import SchedulerService


class _FakeProcessService(ProcessService):
    def __init__(self):
        self.subscription_started = 0

    async def start_seller_subscription_job(self) -> bool:
        self.subscription_started += 1
        return True

    async def wait_until_exit(self, task_id: int) -> None:
        return None


def _keyword_task(task_id: int, *, enabled: bool = True, cron: str = "0 8 * * *") -> Task:
    return Task(
        id=task_id,
        task_name=f"task-{task_id}",
        enabled=enabled,
        keyword="macbook",
        max_pages=1,
        personal_only=True,
        cron=cron,
        ai_prompt_base_file="prompts/base_prompt.txt",
        ai_prompt_criteria_file="prompts/criteria.txt",
    )


def test_reload_seller_subscription_job_adds_job_when_enabled():
    process = _FakeProcessService()
    scheduler = SchedulerService(process)

    asyncio.run(
        scheduler.reload_seller_subscription_job(
            {"enabled": True, "cron": "0 8 * * *"}
        )
    )
    job = scheduler.scheduler.get_job("seller_subscriptions")
    assert job is not None
    assert job.name == "Scheduled: seller subscriptions"


def test_reload_seller_subscription_job_removes_job_when_disabled():
    process = _FakeProcessService()
    scheduler = SchedulerService(process)

    asyncio.run(
        scheduler.reload_seller_subscription_job(
            {"enabled": True, "cron": "0 8 * * *"}
        )
    )
    asyncio.run(
        scheduler.reload_seller_subscription_job(
            {"enabled": False, "cron": "0 8 * * *"}
        )
    )
    assert scheduler.scheduler.get_job("seller_subscriptions") is None


def test_reload_seller_subscription_job_replaces_existing_cron():
    process = _FakeProcessService()
    scheduler = SchedulerService(process)

    asyncio.run(
        scheduler.reload_seller_subscription_job(
            {"enabled": True, "cron": "0 8 * * *"}
        )
    )
    asyncio.run(
        scheduler.reload_seller_subscription_job(
            {"enabled": True, "cron": "0 9 * * *"}
        )
    )
    jobs = [job.id for job in scheduler.scheduler.get_jobs()]
    assert jobs == ["seller_subscriptions"]


def test_run_seller_subscriptions_triggers_process_service():
    process = _FakeProcessService()
    scheduler = SchedulerService(process)

    asyncio.run(scheduler._run_seller_subscriptions())
    assert process.subscription_started == 1


def test_reload_jobs_keeps_seller_subscription_job():
    process = _FakeProcessService()
    scheduler = SchedulerService(process)

    asyncio.run(
        scheduler.reload_seller_subscription_job(
            {"enabled": True, "cron": "0 1 * * *"}
        )
    )
    asyncio.run(scheduler.reload_jobs([]))
    assert scheduler.scheduler.get_job("seller_subscriptions") is not None

    asyncio.run(scheduler.reload_jobs([_keyword_task(1)]))
    assert scheduler.scheduler.get_job("seller_subscriptions") is not None
    assert scheduler.scheduler.get_job("task_1") is not None


def test_reload_jobs_keeps_xhs_monitor_job():
    process = _FakeProcessService()
    scheduler = SchedulerService(process)
    asyncio.run(scheduler.reload_xhs_job({"enabled": True, "cron": "0 * * * *"}))
    asyncio.run(scheduler.reload_jobs([_keyword_task(1)]))
    job = scheduler.scheduler.get_job("xhs_monitor")
    assert job is not None
    assert job.misfire_grace_time == 3600
    asyncio.run(scheduler.reload_xhs_job({"enabled": False, "cron": "0 * * * *"}))
    assert scheduler.scheduler.get_job("xhs_monitor") is None


def test_reload_jobs_replaces_keyword_jobs_without_removing_subscription():
    process = _FakeProcessService()
    scheduler = SchedulerService(process)

    asyncio.run(
        scheduler.reload_seller_subscription_job(
            {"enabled": True, "cron": "0 1 * * *"}
        )
    )
    asyncio.run(scheduler.reload_jobs([_keyword_task(99)]))
    assert scheduler.scheduler.get_job("task_99") is not None

    asyncio.run(scheduler.reload_jobs([_keyword_task(1)]))
    assert scheduler.scheduler.get_job("task_99") is None
    assert scheduler.scheduler.get_job("task_1") is not None
    assert scheduler.scheduler.get_job("seller_subscriptions") is not None


def test_get_seller_subscription_next_run_time_none_when_job_missing():
    scheduler = SchedulerService(_FakeProcessService())
    assert scheduler.get_seller_subscription_next_run_time() is None


def test_get_seller_subscription_next_run_time_reads_mounted_job():
    scheduler = SchedulerService(_FakeProcessService())
    asyncio.run(
        scheduler.reload_seller_subscription_job(
            {"enabled": True, "cron": "0 1 * * *"}
        )
    )
    next_run = scheduler.get_seller_subscription_next_run_time()
    assert next_run is not None


def test_seller_subscription_job_allows_hour_misfire_grace():
    from src.services.scheduler_service import DAILY_JOB_MISFIRE_GRACE_SECONDS

    scheduler = SchedulerService(_FakeProcessService())
    asyncio.run(
        scheduler.reload_seller_subscription_job(
            {"enabled": True, "cron": "0 9 * * *"}
        )
    )
    job = scheduler.scheduler.get_job("seller_subscriptions")
    assert job.misfire_grace_time == DAILY_JOB_MISFIRE_GRACE_SECONDS
    assert DAILY_JOB_MISFIRE_GRACE_SECONDS >= 3600
    assert job.coalesce is True


def test_keyword_and_health_jobs_share_misfire_grace():
    from src.services.scheduler_service import DAILY_JOB_MISFIRE_GRACE_SECONDS

    scheduler = SchedulerService(_FakeProcessService())
    asyncio.run(scheduler.reload_jobs([_keyword_task(1, cron="0 12 * * *")]))
    scheduler.reload_monitor_health_job("0 9 * * 1")
    keyword_job = scheduler.scheduler.get_job("task_1")
    health_job = scheduler.scheduler.get_job("item_monitor_health_weekly")
    assert keyword_job.misfire_grace_time == DAILY_JOB_MISFIRE_GRACE_SECONDS
    assert health_job.misfire_grace_time == DAILY_JOB_MISFIRE_GRACE_SECONDS


def test_cron_trigger_actually_fires_after_two_seconds():
    """与线上相同的 AsyncIOScheduler + 6 段 Cron，确认短延迟会触发。"""
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from src.core.cron_utils import build_cron_trigger
    from src.services.scheduler_service import DAILY_JOB_MISFIRE_GRACE_SECONDS

    shanghai = ZoneInfo("Asia/Shanghai")
    fired: list[object] = []

    async def _run() -> None:
        async def probe() -> None:
            fired.append(True)

        started = datetime.now(shanghai) + timedelta(seconds=2)
        cron = f"{started.second} {started.minute} {started.hour} * * *"
        scheduler = AsyncIOScheduler(timezone=shanghai)
        scheduler.add_job(
            probe,
            trigger=build_cron_trigger(cron, timezone=shanghai),
            id="probe",
            misfire_grace_time=DAILY_JOB_MISFIRE_GRACE_SECONDS,
            coalesce=True,
            max_instances=1,
            replace_existing=True,
        )
        scheduler.start()
        await asyncio.sleep(4)
        if scheduler.running:
            scheduler.shutdown(wait=False)

    asyncio.run(_run())
    assert fired, "2 秒后的 Cron 没有触发，定时器本身有问题"

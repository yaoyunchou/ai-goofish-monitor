"""SchedulerService 单元测试（阶段三：卖家订阅定时任务）。"""
import asyncio

from src.domain.models.task import Task
from src.services.process_service import ProcessService
from src.services.scheduler_service import SchedulerService


class _FakeProcessService(ProcessService):
    def __init__(self):
        self.subscription_started = 0

    async def start_seller_subscription_job(self) -> bool:
        self.subscription_started += 1
        return True


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

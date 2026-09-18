import asyncio

import src.app as app_module


class _FakeTaskService:
    def __init__(self, _repo):
        self.updated = []

    async def get_all_tasks(self):
        return []

    async def update_task_status(self, task_id, is_running):
        self.updated.append((task_id, is_running))


class _FakeSchedulerService:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.reload_payload = None
        self.subscription_schedule = None
        self.monitor_health_reloaded = False

    async def reload_jobs(self, tasks):
        self.reload_payload = list(tasks)

    async def reload_seller_subscription_job(self, schedule):
        self.subscription_schedule = schedule

    def reload_monitor_health_job(self, cron=None):
        """lifespan 启动时会加载商品监控健康度周判定 job。"""
        self.monitor_health_reloaded = True
        return True

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class _FakeProcessService:
    def __init__(self):
        self.stop_all_called = False

    async def stop_all(self):
        self.stop_all_called = True


def test_lifespan_cleans_task_logs_on_startup(monkeypatch, offline_db):
    called = {}
    fake_scheduler = _FakeSchedulerService()
    fake_process = _FakeProcessService()

    monkeypatch.setattr(app_module, "scheduler_service", fake_scheduler)
    monkeypatch.setattr(app_module, "process_service", fake_process)
    monkeypatch.setattr(app_module, "TaskService", _FakeTaskService)
    monkeypatch.setattr(app_module, "create_task_repository", lambda: object())
    async def _no_migrate():
        return 0

    async def _noop_running(_value):
        return {}

    async def _empty_schedule():
        return {}

    monkeypatch.setattr(app_module, "migrate_legacy_subscription_tasks", _no_migrate)
    monkeypatch.setattr(app_module, "set_subscription_running", _noop_running)
    monkeypatch.setattr(app_module, "get_schedule", _empty_schedule)
    monkeypatch.setattr(app_module, "bootstrap_storage", lambda: called.setdefault("bootstrapped", True))
    # lifespan 还会调用 migrate_legacy_subscription_tasks()，它内部自行
    # create_task_repository()，无法被上面的 stub 覆盖；用 offline_db 让该路径
    # 走真实仓储代码 + 内存 SQLite，而不是去连 Supabase。
    monkeypatch.setattr(
        app_module,
        "cleanup_task_logs",
        lambda *args, **kwargs: called.setdefault("keep_days", kwargs.get("keep_days")),
    )
    monkeypatch.setattr(app_module.app_settings, "task_log_retention_days", 9)

    async def _run():
        async with app_module.lifespan(None):
            assert fake_scheduler.started is True
            assert fake_scheduler.reload_payload == []

    asyncio.run(_run())

    assert called["bootstrapped"] is True
    assert called["keep_days"] == 9
    assert fake_scheduler.stopped is True
    assert fake_process.stop_all_called is True

from src.domain.seller_subscription import enrich_schedule, resolve_schedule_run_headless


def test_resolve_schedule_run_headless_uses_env_when_unset(monkeypatch):
    monkeypatch.setattr("src.domain.seller_subscription.RUN_HEADLESS", True)
    assert resolve_schedule_run_headless({}) is True
    assert resolve_schedule_run_headless({"run_headless": None}) is True


def test_resolve_schedule_run_headless_honors_explicit_value(monkeypatch):
    monkeypatch.setattr("src.domain.seller_subscription.RUN_HEADLESS", True)
    assert resolve_schedule_run_headless({"run_headless": False}) is False
    assert resolve_schedule_run_headless({"run_headless": True}) is True


def test_enrich_schedule_adds_effective_flag(monkeypatch):
    monkeypatch.setattr("src.domain.seller_subscription.RUN_HEADLESS", False)
    payload = enrich_schedule({"cron": "0 8 * * *"})
    assert payload["run_headless_effective"] is False

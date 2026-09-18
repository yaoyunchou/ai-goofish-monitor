from src.domain import seller_subscription as sub_mod
from src.domain.seller_subscription import is_seller_subscription_console_log_enabled


def test_console_log_flag_reads_config(monkeypatch):
    monkeypatch.setattr(sub_mod, "SELLER_SUBSCRIPTION_CONSOLE_LOG", False)
    assert is_seller_subscription_console_log_enabled() is False
    monkeypatch.setattr(sub_mod, "SELLER_SUBSCRIPTION_CONSOLE_LOG", True)
    assert is_seller_subscription_console_log_enabled() is True

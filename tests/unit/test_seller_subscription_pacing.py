from src.domain.seller_subscription_pacing import (
    SubscriptionPacing,
    SubscriptionPacingConfig,
)


def test_pacing_config_defaults():
    config = SubscriptionPacingConfig.from_mapping(None)
    assert config.batch_size == 10
    assert config.detail_delay_min == 4.0


def test_pacing_estimate_scales_with_sellers_and_items():
    config = SubscriptionPacingConfig.from_mapping({"batch_size": 10})
    small = config.estimate_seconds(1, 10)
    large = config.estimate_seconds(5, 100)
    assert large > small * 10


def test_pacing_from_task_config():
    pacing = SubscriptionPacing.from_task_config(
        {"pacing": {"batch_size": 5, "detail_delay_min": 2.0, "detail_delay_max": 4.0}}
    )
    assert pacing.config.batch_size == 5


def test_shuffle_items_changes_order_but_keeps_length():
    items = [{"商品ID": str(i)} for i in range(5)]
    shuffled = SubscriptionPacing.shuffle_items(items)
    assert len(shuffled) == 5
    assert {item["商品ID"] for item in shuffled} == {str(i) for i in range(5)}

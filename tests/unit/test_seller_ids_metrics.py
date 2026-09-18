from src.domain.seller_ids import parse_metric_int, parse_praise_ratio


def test_parse_metric_int_handles_w_suffix():
    assert parse_metric_int("1.1w") == 11000
    assert parse_metric_int("1.1W") == 11000
    assert parse_metric_int("1.2万") == 12000
    assert parse_metric_int("3k") == 3000
    assert parse_metric_int("128") == 128


def test_parse_praise_ratio_strips_percent():
    assert parse_praise_ratio("98%") == 98.0
    assert parse_praise_ratio(99) == 99.0

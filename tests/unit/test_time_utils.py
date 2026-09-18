from datetime import datetime
from zoneinfo import ZoneInfo

from src.time_utils import shanghai_today, to_shanghai_iso


def test_to_shanghai_iso_from_utc_aware():
    utc = datetime(2026, 9, 17, 2, 38, 59, tzinfo=ZoneInfo("UTC"))
    assert to_shanghai_iso(utc) == "2026-09-17T10:38:59+08:00"


def test_to_shanghai_iso_from_naive_string():
    assert to_shanghai_iso("2026-09-17T10:38:59") == "2026-09-17T10:38:59+08:00"


def test_shanghai_today_uses_asia_shanghai():
    fixed = datetime(2026, 9, 16, 23, 30, tzinfo=ZoneInfo("UTC"))
    assert shanghai_today(fixed) == datetime(2026, 9, 17).date()

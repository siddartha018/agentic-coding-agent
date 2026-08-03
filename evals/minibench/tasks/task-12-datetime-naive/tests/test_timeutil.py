from datetime import datetime, timezone
from src.timeutil import is_future_date


def test_future_date():
    # A date far in the future
    assert is_future_date("2099-12-31T00:00:00+00:00") is True


def test_past_date():
    # A date in the past
    assert is_future_date("2000-01-01T00:00:00+00:00") is False

from datetime import datetime


def is_future_date(date_str):
    """Check if a date string (YYYY-MM-DD) represents a future date."""
    target = datetime.fromisoformat(date_str)
    now = datetime.now()
    return target > now

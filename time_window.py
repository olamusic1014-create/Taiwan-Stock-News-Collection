from __future__ import annotations

from datetime import datetime


MIN_DAY_RANGE = 1
MAX_DAY_RANGE = 14
DEFAULT_DAY_RANGE = 7


def clamp_day_range(day_range: int) -> int:
    return max(MIN_DAY_RANGE, min(MAX_DAY_RANGE, int(day_range)))


def is_within_recent_days(date_obj: datetime, day_range: int) -> bool:
    if not date_obj:
        return True
    safe_day_range = clamp_day_range(day_range)
    now = datetime.now(date_obj.tzinfo)
    return (now - date_obj).days <= safe_day_range

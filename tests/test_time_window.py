import unittest
from datetime import datetime, timedelta, timezone

from time_window import (
    DEFAULT_DAY_RANGE,
    MAX_DAY_RANGE,
    MIN_DAY_RANGE,
    clamp_day_range,
    is_within_recent_days,
)


class TimeWindowTests(unittest.TestCase):
    def test_clamp_day_range_enforces_bounds(self):
        self.assertEqual(clamp_day_range(0), MIN_DAY_RANGE)
        self.assertEqual(clamp_day_range(3), 3)
        self.assertEqual(clamp_day_range(99), MAX_DAY_RANGE)

    def test_default_day_range_is_within_supported_bounds(self):
        self.assertGreaterEqual(DEFAULT_DAY_RANGE, MIN_DAY_RANGE)
        self.assertLessEqual(DEFAULT_DAY_RANGE, MAX_DAY_RANGE)

    def test_is_within_recent_days_respects_selected_window(self):
        now = datetime.now(timezone.utc)
        self.assertTrue(is_within_recent_days(now - timedelta(days=2), 2))
        self.assertFalse(is_within_recent_days(now - timedelta(days=3, seconds=1), 2))


if __name__ == "__main__":
    unittest.main()

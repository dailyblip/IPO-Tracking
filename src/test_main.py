import unittest
from datetime import date

from main import _default_lookback_days


class LookbackTests(unittest.TestCase):
    def test_monday_includes_thursday_and_friday(self):
        self.assertEqual(_default_lookback_days(date(2026, 8, 17)), 4)

    def test_midweek_uses_two_calendar_days(self):
        self.assertEqual(_default_lookback_days(date(2026, 8, 19)), 2)

    def test_sunday_reaches_back_to_thursday(self):
        self.assertEqual(_default_lookback_days(date(2026, 8, 23)), 3)


if __name__ == "__main__":
    unittest.main()

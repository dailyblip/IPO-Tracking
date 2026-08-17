import unittest
from datetime import date
from unittest.mock import patch

import main


class LookbackTests(unittest.TestCase):
    def test_monday_includes_thursday_and_friday(self):
        self.assertEqual(main._default_lookback_days(date(2026, 8, 17)), 4)

    def test_midweek_uses_two_calendar_days(self):
        self.assertEqual(main._default_lookback_days(date(2026, 8, 19)), 2)

    def test_sunday_reaches_back_to_thursday(self):
        self.assertEqual(main._default_lookback_days(date(2026, 8, 23)), 3)

    @patch("main.filing_parser.parse_filing")
    @patch("main.edgar_client.find_matching_s1", return_value={})
    @patch("main.edgar_client.is_first_time_registrant", return_value=True)
    @patch("main.edgar_client.is_us_based", return_value=True)
    def test_skips_filer_without_domestic_s1(self, _us, _first, _s1, parse_filing):
        rows = main.process_filing({
            "company_name": "Foreign Issuer",
            "cik": "2006960",
            "accession_no": "0001193125-26-351136",
        })
        self.assertEqual(rows, [])
        parse_filing.assert_not_called()


if __name__ == "__main__":
    unittest.main()

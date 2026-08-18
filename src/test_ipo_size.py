import unittest
from pathlib import Path

import s1_monitor


class IpoSizeTests(unittest.TestCase):
    def test_extracts_stated_aggregate_ipo_size(self):
        value = s1_monitor._extract_ipo_size(
            "Proposed Maximum Aggregate Offering Price $100,000,000",
            {},
            {},
        )
        self.assertEqual(value, 100_000_000)

    def test_derives_size_from_shares_and_preliminary_range(self):
        value = s1_monitor._extract_ipo_size(
            "Initial public offering",
            {"cover_page": {"offering_size_shares": 5_000_000}},
            {"range_low": 18, "range_high": 20},
        )
        self.assertEqual(value, 95_000_000)

    def test_queue_uses_ipo_size_as_dashboard_value(self):
        queued = s1_monitor._queue_record({
            "company": "Example Corp",
            "cik": "1234567",
            "ipo_size": 100_000_000,
        })
        self.assertEqual(queued["ipo_size"], 100_000_000)
        self.assertEqual(queued["value"], 100_000_000)

    def test_dashboard_has_merged_ipo_size_offering_value_column(self):
        html = Path(__file__).resolve().parents[1].joinpath("docs", "index.html").read_text(encoding="utf-8")
        self.assertIn("<th>IPO Size / Offering Value</th>", html)
        self.assertIn("money(filing.ipo_size||filing.value)", html)


if __name__ == "__main__":
    unittest.main()

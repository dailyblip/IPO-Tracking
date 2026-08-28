import unittest
from pathlib import Path

import s1_monitor


class IpoSizeTests(unittest.TestCase):
    def test_rejects_registration_fee_aggregate_as_ipo_size(self):
        value = s1_monitor._extract_ipo_size(
            "Proposed Maximum Aggregate Offering Price $100,000,000",
            {},
            {},
        )
        self.assertIsNone(value)

    def test_derives_size_from_high_confidence_cover_terms(self):
        value = s1_monitor._extract_ipo_size(
            "Initial public offering",
            {
                "cover_page": {
                    "offering_size_shares": 6_000_000,
                    "offering_size_confidence": "High",
                    "offering_size_conflict": False,
                }
            },
            {"range_low": 18, "range_high": 20},
        )
        self.assertEqual(value, 114_000_000)

    def test_queue_uses_canonical_dashboard_value_for_ipo_size(self):
        queued = s1_monitor._queue_record({
            "company": "Example Corp",
            "cik": "1234567",
            "ipo_size": 95_000_000,
        })
        self.assertEqual(queued["value"], 95_000_000)
        self.assertNotIn("ipo_size", queued)

    def test_dashboard_has_merged_ipo_size_offering_value_column(self):
        html = Path(__file__).resolve().parents[1].joinpath("docs", "index.html").read_text(encoding="utf-8")
        self.assertIn(">IPO Size / Offering Value</th>", html)
        self.assertIn("money(filing.ipo_size||filing.value)", html)


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from public_feed_policy import enforce_public_feed_policy


class PublicPersonShareDerivativeTests(unittest.TestCase):
    def _run_policy(self, person):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "filings": [
                    {
                        "id": "standard-nuclear-regression",
                        "company": "Standard Nuclear, Inc.",
                        "form": "424B4",
                        "filed": "2026-07-16",
                        "filing_date": "2026-07-08",
                        "pricing_date": "2026-07-16",
                        "stage": "Priced",
                        "value": 150_000_000,
                        "offering_price": 15.0,
                        "current_price": 18.81,
                        "people": [person],
                    }
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")
            filtered, removed = enforce_public_feed_policy(output)
            self.assertEqual(removed, 0)
            return filtered["filings"][0]["people"][0]

    def test_percentage_like_share_counts_clear_all_unsupported_derivatives(self):
        person = self._run_policy(
            {
                "name": "The Mayhill Trust",
                "shares": 6.6,
                "shares_sold_ipo": 6.6,
                "liquid_shares": 6.6,
                "locked_shares": 6.6,
                "cash_value": 124.146,
                "ipo_value": 99.0,
                "cash_realized_ipo": 99.0,
                "liquid_value": 124.146,
                "locked_value": 124.146,
                "valuation_as_of": "2026-08-28",
            }
        )

        self.assertIsNone(person["shares"])
        self.assertIsNone(person["shares_sold_ipo"])
        self.assertIsNone(person["liquid_shares"])
        self.assertIsNone(person["locked_shares"])
        for field in (
            "cash_value",
            "ipo_value",
            "cash_realized_ipo",
            "liquid_value",
            "locked_value",
            "valuation_as_of",
        ):
            self.assertIsNone(person[field], field)

    def test_missing_share_basis_clears_stale_ipo_value(self):
        person = self._run_policy(
            {
                "name": "Entities affiliated with Decisive Point Group",
                "shares": None,
                "shares_before_ipo": None,
                "shares_sold_ipo": None,
                "shares_after_ipo": None,
                "ipo_value": 99.0,
            }
        )
        self.assertIsNone(person["shares"])
        self.assertIsNone(person["ipo_value"])

    def test_supported_share_counts_keep_supported_derivatives(self):
        person = self._run_policy(
            {
                "name": "Jane Example",
                "shares": 1_000,
                "shares_sold_ipo": 100,
                "liquid_shares": 200,
                "locked_shares": 800,
                "cash_value": 1.0,
                "ipo_value": 15_000.0,
                "cash_realized_ipo": 1_500.0,
                "liquid_value": 1.0,
                "locked_value": 1.0,
            }
        )

        self.assertEqual(person["shares"], 1_000)
        self.assertEqual(person["ipo_value"], 15_000.0)
        self.assertEqual(person["cash_realized_ipo"], 1_500.0)
        self.assertEqual(person["cash_value"], 18_810.0)
        self.assertEqual(person["liquid_value"], 3_762.0)
        self.assertEqual(person["locked_value"], 15_048.0)


if __name__ == "__main__":
    unittest.main()

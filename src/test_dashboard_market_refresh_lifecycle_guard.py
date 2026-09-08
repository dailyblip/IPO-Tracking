import json
import tempfile
import unittest
from pathlib import Path

from dashboard_export import refresh_market_prices


class DashboardMarketRefreshLifecycleGuardTests(unittest.TestCase):
    def test_same_ticker_quote_updates_only_priced_ipo(self):
        payload = {
            "schema_version": 1,
            "generated_at": "2026-08-11T00:00:00+00:00",
            "source": "SEC EDGAR",
            "filings": [
                {
                    "id": "priced",
                    "company": "Priced Example",
                    "ticker": "DUP",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-08-11",
                    "pricing_date": "2026-08-10",
                    "offering_price": 20.0,
                    "people": [{"name": "Priced Holder", "shares": 10}],
                },
                {
                    "id": "prepricing",
                    "company": "Pending Example",
                    "ticker": "DUP",
                    "form": "S-1/A",
                    "stage": "Pre-pricing",
                    "filed": "2026-08-11",
                    "pricing_date": None,
                    "offering_price": None,
                    "people": [{"name": "Pending Holder", "shares": 20}],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            output.write_text(json.dumps(payload), encoding="utf-8")

            refreshed = refresh_market_prices(
                output,
                {"DUP": 25.0},
                updated_at="2026-08-12T00:00:00+00:00",
            )

        priced, prepricing = refreshed["filings"]
        self.assertEqual(priced["current_price"], 25.0)
        self.assertEqual(priced["people"][0]["cash_value"], 250.0)
        self.assertNotIn("current_price", prepricing)
        self.assertNotIn("price_updated", prepricing)
        self.assertNotIn("cash_value", prepricing["people"][0])
        self.assertNotIn("valuation_as_of", prepricing["people"][0])


if __name__ == "__main__":
    unittest.main()

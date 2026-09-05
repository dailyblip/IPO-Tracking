import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from dashboard_export import refresh_market_prices
from price_lookup import QuotePrice, _validate_quote


class MarketQuoteProviderTimestampTests(unittest.TestCase):
    def test_validated_quote_preserves_provider_timestamp(self):
        now = 2_000_000_000
        quote = _validate_quote("TEST", {"c": 42.5, "t": now - 60}, now=now)

        self.assertIsInstance(quote, float)
        self.assertEqual(quote, 42.5)
        self.assertEqual(quote.quote_timestamp, now - 60)

    def test_refresh_uses_provider_time_for_quote_and_holder_valuation(self):
        provider_time = datetime(2026, 8, 18, 14, 30, tzinfo=timezone.utc)
        retrieval_time = "2026-08-18T15:00:00+00:00"
        payload = {
            "schema_version": 1,
            "generated_at": "2026-08-17T00:00:00+00:00",
            "source": "SEC EDGAR",
            "filings": [
                {
                    "id": "example",
                    "ticker": "ACME",
                    "current_price": 24.5,
                    "price_updated": "2026-08-17T20:00:00+00:00",
                    "people": [
                        {
                            "name": "Jane Founder",
                            "shares": 2_000_000,
                            "cash_value": 49_000_000,
                            "valuation_as_of": "2026-08-17T20:00:00+00:00",
                        }
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            output.write_text(json.dumps(payload), encoding="utf-8")

            refreshed = refresh_market_prices(
                output,
                {"ACME": QuotePrice(31.25, provider_time.timestamp())},
                updated_at=retrieval_time,
            )

            filing = refreshed["filings"][0]
            person = filing["people"][0]
            self.assertEqual(filing["current_price"], 31.25)
            self.assertEqual(filing["price_updated"], provider_time.isoformat())
            self.assertEqual(person["cash_value"], 62_500_000)
            self.assertEqual(person["valuation_as_of"], provider_time.isoformat())
            self.assertEqual(refreshed["generated_at"], retrieval_time)


if __name__ == "__main__":
    unittest.main()

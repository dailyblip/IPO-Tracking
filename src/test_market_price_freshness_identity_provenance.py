import unittest

from market_price_freshness_gate import sanitize_payload


class MarketPriceFreshnessIdentityProvenanceTests(unittest.TestCase):
    def _fresh_priced_quote(self):
        return {
            "company": "Example Operating Co",
            "ticker": "EXCO",
            "form": "424B4",
            "stage": "Priced",
            "pricing_date": "2026-09-08",
            "filed": "2026-09-09",
            "current_price": 12.34,
            "price_updated": "2026-09-09T14:00:00+00:00",
            "signals": ["Current market value is approximately $12M"],
            "people": [
                {
                    "name": "Example Holder",
                    "cash_value": 1_000_000,
                    "valuation_as_of": "2026-09-09T14:00:00+00:00",
                    "ipo_value": 900_000,
                }
            ],
        }

    def test_fresh_quote_without_ticker_provenance_is_cleared(self):
        filing = self._fresh_priced_quote()
        filing["ticker"] = ""
        payload = {
            "generated_at": "2026-09-09T14:05:00+00:00",
            "filings": [filing],
        }

        sanitized, stale = sanitize_payload(payload)

        self.assertEqual(len(stale), 1)
        filing = sanitized["filings"][0]
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertEqual(filing["signals"], [])
        person = filing["people"][0]
        self.assertNotIn("cash_value", person)
        self.assertNotIn("valuation_as_of", person)
        self.assertEqual(person["ipo_value"], 900_000)

    def test_fresh_quote_with_issuer_and_ticker_provenance_survives(self):
        payload = {
            "generated_at": "2026-09-09T14:05:00+00:00",
            "filings": [self._fresh_priced_quote()],
        }

        sanitized, stale = sanitize_payload(payload)

        self.assertEqual(stale, [])
        filing = sanitized["filings"][0]
        self.assertEqual(filing["current_price"], 12.34)
        self.assertEqual(filing["ticker"], "EXCO")
        self.assertEqual(filing["people"][0]["cash_value"], 1_000_000)


if __name__ == "__main__":
    unittest.main()

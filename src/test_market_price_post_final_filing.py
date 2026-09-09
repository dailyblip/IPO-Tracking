import unittest

from market_price_freshness_gate import sanitize_payload


class MarketPricePostFinalFilingTests(unittest.TestCase):
    def _payload(self, quote_timestamp):
        return {
            "generated_at": "2026-09-09T16:00:00+00:00",
            "filings": [
                {
                    "company": "Example Operating Co",
                    "ticker": "EXCO",
                    "form": "424B4",
                    "stage": "Priced",
                    "pricing_date": "2026-09-08",
                    "filed": "2026-09-09",
                    "current_price": 12.34,
                    "price_updated": quote_timestamp,
                    "signals": ["Current market value is approximately $12M"],
                    "people": [
                        {
                            "name": "Example Holder",
                            "cash_value": 1_000_000,
                            "valuation_as_of": quote_timestamp,
                            "ipo_value": 900_000,
                        }
                    ],
                }
            ],
        }

    def test_quote_after_pricing_but_before_final_424b4_filing_is_cleared(self):
        sanitized, stale = sanitize_payload(
            self._payload("2026-09-08T20:00:00+00:00")
        )

        self.assertEqual(len(stale), 1)
        filing = sanitized["filings"][0]
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertEqual(filing["signals"], [])
        person = filing["people"][0]
        self.assertNotIn("cash_value", person)
        self.assertNotIn("valuation_as_of", person)
        self.assertEqual(person["ipo_value"], 900_000)

    def test_quote_on_final_424b4_filing_date_can_survive(self):
        sanitized, stale = sanitize_payload(
            self._payload("2026-09-09T14:00:00+00:00")
        )

        self.assertEqual(stale, [])
        filing = sanitized["filings"][0]
        self.assertEqual(filing["current_price"], 12.34)
        self.assertEqual(filing["price_updated"], "2026-09-09T14:00:00+00:00")
        self.assertEqual(filing["people"][0]["cash_value"], 1_000_000)


if __name__ == "__main__":
    unittest.main()

import unittest

from market_price_freshness_gate import sanitize_payload


class OrphanMarketDerivativeTests(unittest.TestCase):
    def test_quote_derivatives_without_current_price_fail_closed(self):
        payload = {
            "generated_at": "2026-09-08T07:50:00+00:00",
            "filings": [
                {
                    "company": "Orphan Valuation Co",
                    "ticker": "ORPH",
                    "stage": "Priced",
                    "pricing_date": "2026-09-04",
                    "price_updated": "2026-09-05T20:00:00+00:00",
                    "signals": [
                        "Offering raised approximately $100M",
                        "Largest named holding currently valued at approximately $5M",
                    ],
                    "people": [
                        {
                            "name": "Example Holder",
                            "cash_value": 5_000_000,
                            "liquid_value": 1_000_000,
                            "locked_value": 4_000_000,
                            "valuation_as_of": "2026-09-05T20:00:00+00:00",
                            "ipo_value": 3_500_000,
                        }
                    ],
                }
            ],
        }

        sanitized, stale = sanitize_payload(payload)

        self.assertEqual(len(stale), 1)
        self.assertEqual(
            stale[0]["reason"], "quote-derived values present without current price"
        )
        filing = sanitized["filings"][0]
        self.assertNotIn("price_updated", filing)
        self.assertEqual(filing["signals"], ["Offering raised approximately $100M"])
        person = filing["people"][0]
        for field in ("cash_value", "liquid_value", "locked_value", "valuation_as_of"):
            self.assertNotIn(field, person)
        self.assertEqual(person["ipo_value"], 3_500_000)

    def test_blank_current_price_without_quote_derivatives_is_not_rewritten(self):
        payload = {
            "generated_at": "2026-09-08T07:50:00+00:00",
            "filings": [
                {
                    "company": "IPO Value Only Co",
                    "ticker": "IPOV",
                    "stage": "Priced",
                    "pricing_date": "2026-09-04",
                    "signals": ["Offering raised approximately $100M"],
                    "people": [
                        {
                            "name": "Example Holder",
                            "ipo_value": 3_500_000,
                            "cash_realized_ipo": 250_000,
                        }
                    ],
                }
            ],
        }

        sanitized, stale = sanitize_payload(payload)

        self.assertEqual(stale, [])
        person = sanitized["filings"][0]["people"][0]
        self.assertEqual(person["ipo_value"], 3_500_000)
        self.assertEqual(person["cash_realized_ipo"], 250_000)
        self.assertEqual(
            sanitized["filings"][0]["signals"], ["Offering raised approximately $100M"]
        )


if __name__ == "__main__":
    unittest.main()

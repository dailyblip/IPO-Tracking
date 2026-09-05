import unittest

from prepricing_quote_sanitizer import has_release_safe_market_quote, sanitize_payload


class MissingFinalFilingDateQuoteGuardTests(unittest.TestCase):
    def test_priced_424b4_missing_filed_date_loses_quote_and_holder_derivatives(self):
        payload = {
            "filings": [
                {
                    "company": "Example Holdings Inc.",
                    "form": "424B4",
                    "stage": "Priced",
                    "pricing_date": "2026-08-20",
                    "offering_price": 20.0,
                    "current_price": 24.5,
                    "price_updated": "2026-09-04T20:00:00+00:00",
                    "signals": ["Largest named holding currently valued at $24.5M"],
                    "people": [
                        {
                            "name": "Example Owner",
                            "shares": 1000000,
                            "cash_value": 24500000,
                            "liquid_value": 1000000,
                            "locked_value": 23500000,
                            "valuation_as_of": "2026-09-04",
                        }
                    ],
                }
            ]
        }

        self.assertFalse(has_release_safe_market_quote(payload["filings"][0]))
        cleaned, changed = sanitize_payload(payload)

        self.assertEqual(changed, 1)
        filing = cleaned["filings"][0]
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertEqual(filing["signals"], [])
        person = filing["people"][0]
        self.assertEqual(person["shares"], 1000000)
        for field in ("cash_value", "liquid_value", "locked_value", "valuation_as_of"):
            self.assertNotIn(field, person)

    def test_valid_priced_424b4_with_canonical_filed_date_keeps_quote(self):
        payload = {
            "filings": [
                {
                    "company": "Example Holdings Inc.",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-08-21",
                    "pricing_date": "2026-08-20",
                    "offering_price": 20.0,
                    "current_price": 24.5,
                    "price_updated": "2026-09-04T20:00:00+00:00",
                    "people": [{"name": "Example Owner", "cash_value": 24500000}],
                }
            ]
        }

        self.assertTrue(has_release_safe_market_quote(payload["filings"][0]))
        cleaned, changed = sanitize_payload(payload)

        self.assertEqual(changed, 0)
        self.assertEqual(cleaned["filings"][0]["current_price"], 24.5)
        self.assertEqual(cleaned["filings"][0]["people"][0]["cash_value"], 24500000)


if __name__ == "__main__":
    unittest.main()

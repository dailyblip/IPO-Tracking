import unittest

from prepricing_quote_sanitizer import sanitize_payload


class PrepricingQuoteSanitizerTests(unittest.TestCase):
    def test_removes_market_quotes_from_s1_record(self):
        payload = {
            "filings": [{
                "id": "s1:1",
                "form": "S-1/A",
                "stage": "Pre-pricing",
                "ticker": "LYNX",
                "current_price": 13.65,
                "price_updated": "2026-08-26T20:05:29+00:00",
                "people": [{
                    "name": "Example Owner",
                    "cash_value": 123,
                    "liquid_value": 45,
                    "locked_value": 78,
                    "valuation_as_of": "2026-08-26",
                }],
            }]
        }
        sanitized, changed = sanitize_payload(payload)
        filing = sanitized["filings"][0]
        self.assertEqual(changed, 1)
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertNotIn("cash_value", filing["people"][0])
        self.assertNotIn("valuation_as_of", filing["people"][0])

    def test_preserves_market_quote_for_complete_final_424b4(self):
        payload = {
            "filings": [{
                "id": "priced-1",
                "form": "424B4",
                "stage": "Priced",
                "pricing_date": "2026-08-26",
                "offering_price": 18.0,
                "current_price": 24.13,
                "price_updated": "2026-08-26T20:05:29+00:00",
                "people": [{"cash_value": 100}],
            }]
        }
        sanitized, changed = sanitize_payload(payload)
        filing = sanitized["filings"][0]
        self.assertEqual(changed, 0)
        self.assertEqual(filing["current_price"], 24.13)
        self.assertEqual(filing["people"][0]["cash_value"], 100)

    def test_removes_quote_from_424b4_with_prepricing_stage(self):
        payload = {
            "filings": [{
                "id": "malformed-stage",
                "form": "424B4",
                "stage": "Pre-pricing",
                "pricing_date": "2026-08-26",
                "offering_price": 18.0,
                "current_price": 24.13,
                "price_updated": "2026-08-26T20:05:29+00:00",
                "people": [{"cash_value": 100, "valuation_as_of": "2026-08-26"}],
            }]
        }
        sanitized, changed = sanitize_payload(payload)
        filing = sanitized["filings"][0]
        self.assertEqual(changed, 1)
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertNotIn("cash_value", filing["people"][0])
        self.assertNotIn("valuation_as_of", filing["people"][0])

    def test_removes_quote_from_incomplete_priced_424b4(self):
        cases = (
            {"pricing_date": None, "offering_price": 18.0},
            {"pricing_date": "2026-08-26", "offering_price": None},
            {"pricing_date": "not-a-date", "offering_price": 18.0},
            {"pricing_date": "2026-08-26", "offering_price": 0},
        )
        for index, fields in enumerate(cases):
            with self.subTest(fields=fields):
                payload = {
                    "filings": [{
                        "id": f"incomplete-{index}",
                        "form": "424B4",
                        "stage": "Priced",
                        "current_price": 24.13,
                        "price_updated": "2026-08-26T20:05:29+00:00",
                        "people": [{"cash_value": 100}],
                        **fields,
                    }]
                }
                sanitized, changed = sanitize_payload(payload)
                filing = sanitized["filings"][0]
                self.assertEqual(changed, 1)
                self.assertNotIn("current_price", filing)
                self.assertNotIn("cash_value", filing["people"][0])


if __name__ == "__main__":
    unittest.main()

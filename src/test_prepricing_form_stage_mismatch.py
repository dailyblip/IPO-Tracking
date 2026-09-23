import unittest

from prepricing_quote_sanitizer import sanitize_payload


class PrepricingFormStageMismatchTests(unittest.TestCase):
    def test_s1_with_stale_priced_stage_cannot_retain_final_pricing_or_quote_fields(self):
        payload = {
            "filings": [{
                "id": "stale-s1-lifecycle",
                "form": "S-1/A",
                "stage": "Priced",
                "ticker": "TEST",
                "filing_price": "$14.00–$16.00",
                "price_range": "$14.00–$16.00",
                "offering_price": 18.0,
                "current_price": 21.25,
                "price_updated": "2026-09-22T20:05:29+00:00",
                "signals": [
                    "Preliminary offering range disclosed at $14.00–$16.00",
                    "Offering priced at $18.00 per share",
                    "Offering raised approximately $180M",
                    "Largest named holding currently valued at approximately $21M",
                ],
                "people": [{
                    "name": "Example Owner",
                    "shares": 1_000_000,
                    "ownership_percent": 8.0,
                    "ipo_value": 18_000_000.0,
                    "cash_realized_ipo": 2_000_000.0,
                    "cash_value": 21_250_000.0,
                    "valuation_as_of": "2026-09-22",
                }],
            }]
        }

        sanitized, changed = sanitize_payload(payload)
        filing = sanitized["filings"][0]
        person = filing["people"][0]

        self.assertEqual(changed, 1)
        self.assertEqual(filing["filing_price"], "$14.00–$16.00")
        self.assertEqual(filing["price_range"], "$14.00–$16.00")
        self.assertNotIn("offering_price", filing)
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertEqual(person["shares"], 1_000_000)
        self.assertEqual(person["ownership_percent"], 8.0)
        self.assertNotIn("ipo_value", person)
        self.assertNotIn("cash_realized_ipo", person)
        self.assertNotIn("cash_value", person)
        self.assertNotIn("valuation_as_of", person)
        self.assertEqual(
            filing["signals"],
            ["Preliminary offering range disclosed at $14.00–$16.00"],
        )


if __name__ == "__main__":
    unittest.main()

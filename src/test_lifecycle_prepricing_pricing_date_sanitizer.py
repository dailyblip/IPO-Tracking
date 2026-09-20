import unittest

import lifecycle_date_sanitizer as sanitizer


class PrepricingPricingDateSanitizerTests(unittest.TestCase):
    def test_clears_stale_prepricing_pricing_date_but_preserves_filing_price(self):
        payload = {"filings": [{
            "company": "Still Pre-pricing Co",
            "form": "S-1/A",
            "stage": "Pre-pricing",
            "filed": "2026-09-18",
            "filing_date": "2026-09-10",
            "pricing_date": "2026-09-17",
            "filing_price": "14-16",
        }]}

        cleaned, changed = sanitizer.sanitize_payload(payload)

        self.assertEqual(changed, 1)
        row = cleaned["filings"][0]
        self.assertIsNone(row["pricing_date"])
        self.assertEqual(row["filing_price"], "14-16")
        self.assertEqual(row["filing_date"], "2026-09-10")

    def test_preserves_valid_priced_424b4_pricing_date(self):
        payload = {"filings": [{
            "company": "Priced Co",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-09-18",
            "filing_date": "2026-09-10",
            "pricing_date": "2026-09-17",
            "offering_price": 15.0,
        }]}

        cleaned, changed = sanitizer.sanitize_payload(payload)

        self.assertEqual(changed, 0)
        self.assertEqual(cleaned["filings"][0]["pricing_date"], "2026-09-17")


if __name__ == "__main__":
    unittest.main()

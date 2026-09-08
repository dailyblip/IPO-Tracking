import unittest

from final_pricing_release_gate import is_release_grade_final, sanitize_payload


class PrepricingCurrentPriceReleaseGateTests(unittest.TestCase):
    def _prepricing(self, **overrides):
        filing = {
            "company": "Example Operating Co.",
            "cik": "0001234567",
            "form": "S-1/A",
            "stage": "Pre-pricing",
            "filed": "2026-09-08",
            "pricing_date": None,
            "offering_price": None,
            "current_price": None,
        }
        filing.update(overrides)
        return filing

    def test_prepricing_row_with_live_current_price_is_not_release_grade(self):
        filing = self._prepricing(
            ticker="EXMP",
            current_price=18.42,
            price_updated="2026-09-08T19:30:00+00:00",
        )

        self.assertFalse(is_release_grade_final(filing))
        sanitized, removed = sanitize_payload({"filings": [filing]})
        self.assertEqual(sanitized["filings"], [])
        self.assertEqual(removed, [filing])

    def test_prepricing_row_without_current_price_remains_release_grade(self):
        filing = self._prepricing(ticker="EXMP")

        self.assertTrue(is_release_grade_final(filing))
        sanitized, removed = sanitize_payload({"filings": [filing]})
        self.assertEqual(sanitized["filings"], [filing])
        self.assertEqual(removed, [])


if __name__ == "__main__":
    unittest.main()

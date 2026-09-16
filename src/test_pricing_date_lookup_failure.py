import unittest

import pricing_date_reconciler


class PricingDateLookupFailureTests(unittest.TestCase):
    def test_loader_failure_clears_unverified_sec_filing_date_fallback(self):
        payload = {
            "filings": [
                {
                    "id": "unverified-date-final",
                    "company": "Example Inc.",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-08-19",
                    "pricing_date": "2026-08-19",
                    "offering_price": 17.5,
                }
            ]
        }

        def unavailable_loader(_filing):
            raise RuntimeError("SEC lookup unavailable")

        reconciled, changed, checked, failures = pricing_date_reconciler.reconcile_payload(
            payload, soup_loader=unavailable_loader
        )

        self.assertEqual(checked, 1)
        self.assertEqual(len(failures), 1)
        self.assertEqual(changed, 1)
        self.assertIsNone(reconciled["filings"][0]["pricing_date"])
        self.assertIn("generated_at", reconciled)


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

import lifecycle_date_sanitizer as sanitizer


class LifecycleDateSanitizerTests(unittest.TestCase):
    def test_clears_initial_filing_date_that_occurs_after_pricing(self):
        payload = {"filings": [{
            "company": "Historical IPO",
            "form": "424B4",
            "filing_date": "2026-06-29",
            "pricing_date": "2026-02-05",
        }]}
        cleaned, changed = sanitizer.sanitize_payload(payload)
        self.assertEqual(changed, 1)
        self.assertIsNone(cleaned["filings"][0]["filing_date"])
        self.assertEqual(cleaned["filings"][0]["pricing_date"], "2026-02-05")

    def test_clears_initial_filing_date_that_occurs_after_current_sec_row(self):
        payload = {"filings": [{
            "company": "Amended Pre-pricing IPO",
            "form": "S-1/A",
            "filed": "2026-08-15",
            "filing_date": "2026-08-20",
        }]}
        cleaned, changed = sanitizer.sanitize_payload(payload)
        self.assertEqual(changed, 1)
        self.assertIsNone(cleaned["filings"][0]["filing_date"])
        self.assertEqual(cleaned["filings"][0]["filed"], "2026-08-15")

    def test_preserves_valid_chronology(self):
        payload = {"filings": [{
            "company": "Valid IPO",
            "filed": "2026-08-08",
            "filing_date": "2026-08-04",
            "pricing_date": "2026-08-07",
        }]}
        cleaned, changed = sanitizer.sanitize_payload(payload)
        self.assertEqual(changed, 0)
        self.assertEqual(cleaned["filings"][0]["filing_date"], "2026-08-04")

    def test_preserves_valid_prepricing_amendment_chronology(self):
        payload = {"filings": [{
            "company": "Valid Pre-pricing IPO",
            "form": "S-1/A",
            "filed": "2026-08-15",
            "filing_date": "2026-08-10",
        }]}
        cleaned, changed = sanitizer.sanitize_payload(payload)
        self.assertEqual(changed, 0)
        self.assertEqual(cleaned["filings"][0]["filing_date"], "2026-08-10")

    def test_does_not_guess_when_dates_are_missing(self):
        payload = {"filings": [{"company": "Pre-pricing IPO", "filing_date": "2026-08-24"}]}
        cleaned, changed = sanitizer.sanitize_payload(payload)
        self.assertEqual(changed, 0)
        self.assertNotIn("pricing_date", cleaned["filings"][0])


if __name__ == "__main__":
    unittest.main()

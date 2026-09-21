import json
import tempfile
import unittest
from datetime import date, timedelta
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
        self.assertEqual(changed, 2)
        self.assertEqual(cleaned["filings"][0]["stage"], "Priced")
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

    def test_clears_final_pricing_date_that_occurs_after_424b4_filing(self):
        payload = {"filings": [{
            "company": "Impossible Final IPO",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-08-19",
            "filing_date": "2026-08-10",
            "pricing_date": "2026-08-20",
            "offering_price": 17.5,
        }]}
        cleaned, changed = sanitizer.sanitize_payload(payload)
        self.assertEqual(changed, 1)
        self.assertIsNone(cleaned["filings"][0]["pricing_date"])
        self.assertEqual(cleaned["filings"][0]["filed"], "2026-08-19")
        self.assertEqual(cleaned["filings"][0]["filing_date"], "2026-08-10")
        self.assertEqual(cleaned["filings"][0]["offering_price"], 17.5)

    def test_repairs_424b4_stage_drift_without_changing_authoritative_final_facts(self):
        payload = {"filings": [{
            "company": "Stale Stage Final IPO",
            "form": "424B4",
            "stage": "Pre-pricing",
            "filed": "2026-08-19",
            "filing_date": "2026-08-10",
            "pricing_date": "2026-08-18",
            "offering_price": 17.5,
            "filing_price": "$16.00–$18.00",
        }]}
        cleaned, changed = sanitizer.sanitize_payload(payload)
        self.assertEqual(changed, 1)
        row = cleaned["filings"][0]
        self.assertEqual(row["stage"], "Priced")
        self.assertEqual(row["filed"], "2026-08-19")
        self.assertEqual(row["pricing_date"], "2026-08-18")
        self.assertEqual(row["offering_price"], 17.5)
        self.assertEqual(row["filing_price"], "$16.00–$18.00")

    def test_repairs_blank_424b4_stage_from_authoritative_final_form(self):
        payload = {"filings": [{
            "company": "Blank Stage Final IPO",
            "form": "424B4",
            "stage": "",
            "filed": "2026-08-19",
            "pricing_date": "2026-08-18",
            "offering_price": 17.5,
        }]}
        cleaned, changed = sanitizer.sanitize_payload(payload)
        self.assertEqual(changed, 1)
        self.assertEqual(cleaned["filings"][0]["stage"], "Priced")

    def test_does_not_mask_priced_s1_stage_drift_as_prepricing(self):
        payload = {"filings": [{
            "company": "Unresolved Registration Handoff",
            "form": "S-1/A",
            "stage": "Priced",
            "filed": "2026-08-19",
            "filing_date": "2026-08-10",
            "pricing_date": "2026-08-18",
            "filing_price": "$16.00–$18.00",
        }]}
        cleaned, changed = sanitizer.sanitize_payload(payload)
        self.assertEqual(changed, 0)
        row = cleaned["filings"][0]
        self.assertEqual(row["stage"], "Priced")
        self.assertEqual(row["pricing_date"], "2026-08-18")
        self.assertEqual(row["filing_price"], "$16.00–$18.00")

    def test_clears_malformed_nonblank_lifecycle_dates(self):
        payload = {"filings": [{
            "company": "Malformed Lifecycle IPO",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026/08/19",
            "filing_date": "2026-08-10T00:00:00Z",
            "pricing_date": 20260818,
            "offering_price": 17.5,
        }]}
        cleaned, changed = sanitizer.sanitize_payload(payload)
        self.assertEqual(changed, 3)
        row = cleaned["filings"][0]
        self.assertIsNone(row["filed"])
        self.assertIsNone(row["filing_date"])
        self.assertIsNone(row["pricing_date"])
        self.assertEqual(row["offering_price"], 17.5)

    def test_clears_future_lifecycle_dates_without_guessing_replacements(self):
        future = (date.today() + timedelta(days=1)).isoformat()
        payload = {"filings": [{
            "company": "Future-Dated IPO",
            "form": "424B4",
            "stage": "Priced",
            "filed": future,
            "filing_date": future,
            "pricing_date": future,
            "offering_price": 17.5,
        }]}
        cleaned, changed = sanitizer.sanitize_payload(payload)
        self.assertEqual(changed, 3)
        row = cleaned["filings"][0]
        self.assertIsNone(row["filed"])
        self.assertIsNone(row["filing_date"])
        self.assertIsNone(row["pricing_date"])
        self.assertEqual(row["offering_price"], 17.5)

    def test_preserves_blank_lifecycle_dates_without_counting_change(self):
        payload = {"filings": [{
            "company": "Blank Lifecycle IPO",
            "filed": "",
            "filing_date": "",
            "pricing_date": None,
        }]}
        cleaned, changed = sanitizer.sanitize_payload(payload)
        self.assertEqual(changed, 0)
        row = cleaned["filings"][0]
        self.assertEqual(row["filed"], "")
        self.assertEqual(row["filing_date"], "")
        self.assertIsNone(row["pricing_date"])

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

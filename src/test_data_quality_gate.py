import unittest
from unittest.mock import patch

import qc_review


class ResearchMonitorDataQualityGateTests(unittest.TestCase):
    def _review(self, row):
        with patch.object(qc_review, "llm_consistency_check", return_value=[]):
            return qc_review.review_row(dict(row))

    def test_conflicting_offering_share_counts_are_release_blocking(self):
        row = {
            "Company Name": "Acme, Inc.",
            "Ticker": "ACME",
            "Actual Price": 20.0,
            "Current Price": 21.0,
            "Holder Name": "Jane Founder",
            "Shares": 1_000_000,
            "Cash Value": 21_000_000,
            "Offering Size Conflict": True,
            "Offering Size Confidence": "High",
        }
        reviewed = self._review(row)
        self.assertEqual(reviewed["QC Status"], "Needs Review")
        self.assertIn("Conflicting base-offering share counts", reviewed["QC Notes"])

    def test_medium_confidence_offering_size_is_release_blocking(self):
        row = {
            "Company Name": "Acme, Inc.",
            "Ticker": "ACME",
            "Actual Price": 20.0,
            "Current Price": 21.0,
            "Holder Name": "Jane Founder",
            "Shares": 1_000_000,
            "Cash Value": 21_000_000,
            "IPO Size (Shares)": 5_000_000,
            "Offering Size Confidence": "Medium",
        }
        reviewed = self._review(row)
        self.assertEqual(reviewed["QC Status"], "Needs Review")
        self.assertIn("medium-confidence fallback", reviewed["QC Notes"])

    def test_primary_secondary_total_must_reconcile_exactly(self):
        row = {
            "Company Name": "Acme, Inc.",
            "Ticker": "ACME",
            "Actual Price": 20.0,
            "Current Price": 21.0,
            "Holder Name": "Jane Founder",
            "Shares": 1_000_000,
            "Cash Value": 21_000_000,
            "IPO Size (Shares)": 4_900_000,
            "Primary Offering Shares": 4_000_000,
            "Secondary Offering Shares": 1_000_000,
            "Offering Size Confidence": "High",
        }
        reviewed = self._review(row)
        self.assertEqual(reviewed["QC Status"], "Needs Review")
        self.assertIn("IPO shares do not reconcile", reviewed["QC Notes"])

    def test_priced_filing_cannot_publish_without_final_price(self):
        row = {
            "Company Name": "Acme, Inc.",
            "Ticker": "ACME",
            "Actual Price": None,
            "Current Price": 21.0,
            "Holder Name": "Jane Founder",
            "Shares": 1_000_000,
            "Cash Value": 21_000_000,
            "Date of Pricing": "2026-08-20",
        }
        reviewed = self._review(row)
        self.assertEqual(reviewed["QC Status"], "Needs Review")
        self.assertIn("Priced filing is missing final IPO price", reviewed["QC Notes"])

    def test_offering_value_gap_is_flagged_when_exact_inputs_exist(self):
        row = {
            "Company Name": "Acme, Inc.",
            "Ticker": "ACME",
            "Actual Price": 20.0,
            "Current Price": 21.0,
            "Holder Name": "Jane Founder",
            "Shares": 1_000_000,
            "Cash Value": 21_000_000,
            "IPO Size (Shares)": 5_000_000,
            "Amount Raised": None,
            "Offering Size Confidence": "High",
        }
        reviewed = self._review(row)
        self.assertEqual(reviewed["QC Status"], "Needs Review")
        self.assertIn("Offering value missing despite known IPO shares and final price", reviewed["QC Notes"])

    def test_confirmed_stanford_affiliation_requires_support(self):
        row = {
            "Company Name": "Acme, Inc.",
            "Ticker": "ACME",
            "Actual Price": 20.0,
            "Current Price": 21.0,
            "Holder Name": "Jane Founder",
            "Shares": 1_000_000,
            "Cash Value": 21_000_000,
            "Stanford Affiliation Confirmed": True,
            "Stanford Justification": "",
        }
        reviewed = self._review(row)
        self.assertEqual(reviewed["QC Status"], "Needs Review")
        self.assertIn("Stanford affiliation confirmed without supporting source/justification", reviewed["QC Notes"])

    def test_verified_row_passes_when_cross_fields_are_consistent(self):
        row = {
            "Company Name": "Acme, Inc.",
            "Ticker": "ACME",
            "Actual Price": 20.0,
            "Current Price": 21.0,
            "Holder Name": "Jane Founder",
            "Shares": 900_000,
            "Shares Before IPO": 1_000_000,
            "Shares Sold in IPO": 100_000,
            "Shares After IPO": 900_000,
            "Cash Realized IPO": 2_000_000,
            "Cash Value": 18_900_000,
            "IPO Size (Shares)": 5_000_000,
            "Primary Offering Shares": 4_000_000,
            "Secondary Offering Shares": 1_000_000,
            "Offering Size Confidence": "High",
            "Amount Raised": 100_000_000,
        }
        reviewed = self._review(row)
        self.assertEqual(reviewed["QC Status"], "Verified")
        self.assertEqual(reviewed["QC Notes"], "")


if __name__ == "__main__":
    unittest.main()

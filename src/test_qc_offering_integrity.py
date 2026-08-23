import unittest

from qc_review import check_prospect_integrity


class OfferingIntegrityTests(unittest.TestCase):
    def test_conflicting_authoritative_share_counts_are_release_blocking(self):
        row = {
            "IPO Size (Shares)": "9,000,000",
            "Primary Offering Shares": "8,000,000",
            "Secondary Offering Shares": "2,000,000",
            "Offering Size Confidence": "High",
            "Offering Size Conflict": True,
        }

        issues = check_prospect_integrity(row)

        self.assertIn(
            "Conflicting base-offering share counts found on prospectus cover",
            issues,
        )
        self.assertTrue(
            any("IPO shares do not reconcile" in issue for issue in issues),
            issues,
        )

    def test_exact_primary_secondary_total_reconciles_without_false_positive(self):
        row = {
            "IPO Size (Shares)": "10,000,000",
            "Primary Offering Shares": "8,000,000",
            "Secondary Offering Shares": "2,000,000",
            "Offering Size Confidence": "High",
            "Offering Size Conflict": False,
        }

        issues = check_prospect_integrity(row)

        self.assertFalse(
            any("IPO shares do not reconcile" in issue for issue in issues),
            issues,
        )
        self.assertNotIn(
            "Conflicting base-offering share counts found on prospectus cover",
            issues,
        )

    def test_known_components_with_missing_total_are_flagged(self):
        row = {
            "IPO Size (Shares)": None,
            "Primary Offering Shares": "8,000,000",
            "Secondary Offering Shares": "2,000,000",
            "Offering Size Confidence": "High",
            "Offering Size Conflict": False,
        }

        issues = check_prospect_integrity(row)

        self.assertIn(
            "Total IPO shares missing despite known primary and secondary blocks",
            issues,
        )


if __name__ == "__main__":
    unittest.main()

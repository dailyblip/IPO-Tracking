import unittest

from offering_value_reconciler import (
    OfferingValueReconciliationError,
    PRIMARY_SHARES_MARKER,
    SOURCE_MARKER,
    reconcile_record,
)


class PartialPrimaryAggregateRecoveryTests(unittest.TestCase):
    def test_authoritative_aggregate_recovers_proven_primary_only_subtotal(self):
        filing = {
            "company": "Jersey Mike's Subs Inc.",
            "form": "424B4",
            "stage": "Priced",
            "offering_price": 23.0,
            "value": 317_000_007.0,
            "value_label": "$317M",
            "primary_offering_shares": 13_782_609,
            "secondary_offering_shares": None,
            "offering_size_source": "final 424B4 explicit issuer-only THE OFFERING row",
            "offering_size_confidence": "High",
        }

        changed = reconcile_record(filing, 1_000_000_003.0, primary_shares=13_782_609)

        self.assertTrue(changed)
        self.assertEqual(filing["value"], 1_000_000_003)
        self.assertEqual(filing["value_label"], "$1.0B")
        self.assertEqual(filing["primary_offering_shares"], 13_782_609)
        self.assertIsNone(filing["secondary_offering_shares"])
        self.assertIn(SOURCE_MARKER, filing["offering_size_source"])
        self.assertEqual(filing["offering_size_confidence"], "High")

    def test_same_final_filing_primary_evidence_recovers_lost_lifecycle_fields(self):
        filing = {
            "company": "Jersey Mike's Subs Inc.",
            "form": "424B4",
            "stage": "Priced",
            "offering_price": 23.0,
            "value": 317_000_007.0,
            "value_label": "$317M",
            "primary_offering_shares": None,
            "secondary_offering_shares": None,
            "offering_size_source": "lifecycle reconciled final 424B4",
            "offering_size_confidence": "High",
        }

        changed = reconcile_record(filing, 1_000_000_003.0, primary_shares=13_782_609)

        self.assertTrue(changed)
        self.assertEqual(filing["value"], 1_000_000_003)
        self.assertEqual(filing["value_label"], "$1.0B")
        self.assertEqual(filing["primary_offering_shares"], 13_782_609)
        self.assertIsNone(filing["secondary_offering_shares"])
        self.assertIn(SOURCE_MARKER, filing["offering_size_source"])
        self.assertIn(PRIMARY_SHARES_MARKER, filing["offering_size_source"])

    def test_unproven_large_conflict_still_fails_closed(self):
        filing = {
            "company": "Conflict Co.",
            "form": "424B4",
            "stage": "Priced",
            "offering_price": 23.0,
            "value": 317_000_007.0,
            "value_label": "$317M",
            "primary_offering_shares": 13_782_609,
            "secondary_offering_shares": None,
            "offering_size_source": "legacy estimate",
            "offering_size_confidence": "High",
        }

        with self.assertRaises(OfferingValueReconciliationError):
            reconcile_record(filing, 1_000_000_003.0)

    def test_direct_primary_evidence_does_not_rescue_nonmatching_subtotal(self):
        filing = {
            "company": "Mismatch Co.",
            "form": "424B4",
            "stage": "Priced",
            "offering_price": 23.0,
            "value": 300_000_000.0,
            "value_label": "$300M",
            "primary_offering_shares": None,
            "secondary_offering_shares": None,
            "offering_size_source": "lifecycle reconciled final 424B4",
            "offering_size_confidence": "High",
        }

        with self.assertRaises(OfferingValueReconciliationError):
            reconcile_record(filing, 1_000_000_003.0, primary_shares=13_782_609)

    def test_conflicting_direct_primary_evidence_still_fails_closed(self):
        filing = {
            "company": "Share Conflict Co.",
            "form": "424B4",
            "stage": "Priced",
            "offering_price": 23.0,
            "value": 317_000_007.0,
            "value_label": "$317M",
            "primary_offering_shares": 13_782_609,
            "secondary_offering_shares": None,
            "offering_size_source": "final 424B4 explicit issuer-only THE OFFERING row",
            "offering_size_confidence": "High",
        }

        with self.assertRaises(OfferingValueReconciliationError):
            reconcile_record(filing, 1_000_000_003.0, primary_shares=13_782_610)


if __name__ == "__main__":
    unittest.main()

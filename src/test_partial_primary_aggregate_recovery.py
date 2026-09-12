import unittest

from offering_value_reconciler import (
    OfferingValueReconciliationError,
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
            reconcile_record(filing, 1_000_000_003.0, primary_shares=13_782_609)


if __name__ == "__main__":
    unittest.main()

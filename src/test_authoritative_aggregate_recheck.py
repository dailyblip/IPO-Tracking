import unittest
from datetime import date

from offering_value_reconciler import SOURCE_MARKER, _needs_check, reconcile_record


class AuthoritativeAggregateRecheckTests(unittest.TestCase):
    def _jersey_row(self):
        return {
            "company": "Jersey Mike's Franchise Systems, Inc.",
            "form": "424B4",
            "stage": "Priced",
            "pricing_date": "2026-07-29",
            "value": 317_000_007,
            "offering_price": 23,
            "primary_offering_shares": 13_782_609,
            "secondary_offering_shares": None,
            "offering_size_source": (
                "final 424B4 explicit issuer-only THE OFFERING row; "
                f"{SOURCE_MARKER}"
            ),
            "offering_size_confidence": "High",
        }

    def test_aged_authoritative_aggregate_provenance_forces_recheck(self):
        filing = self._jersey_row()
        self.assertTrue(_needs_check(filing, today=date(2026, 9, 13)))

    def test_recheck_restores_sec_aggregate_without_inventing_secondary_shares(self):
        filing = self._jersey_row()
        self.assertTrue(
            reconcile_record(
                filing,
                1_000_000_003,
                primary_shares=13_782_609,
            )
        )
        self.assertEqual(filing["value"], 1_000_000_003)
        self.assertEqual(filing["primary_offering_shares"], 13_782_609)
        self.assertIsNone(filing["secondary_offering_shares"])
        self.assertEqual(filing["offering_size_confidence"], "High")
        self.assertIn(SOURCE_MARKER, filing["offering_size_source"])


if __name__ == "__main__":
    unittest.main()

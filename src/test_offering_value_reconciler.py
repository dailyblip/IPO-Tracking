import unittest
from datetime import date

from offering_value_reconciler import (
    OfferingValueReconciliationError,
    SOURCE_MARKER,
    _needs_check,
    extract_authoritative_aggregate,
    reconcile_record,
)


class AuthoritativeOfferingValueTests(unittest.TestCase):
    def test_extracts_erock_final_424b4_aggregate(self):
        text = """
        Per Share Total
        Initial public offering price $ 21.50000 $ 600,000,006
        Underwriting discounts and commissions $ 1.34375 $ 37,500,000
        Proceeds, before expenses, to us $ 20.15625 $ 562,500,006
        """
        self.assertEqual(extract_authoritative_aggregate(text, expected_price=21.50), 600_000_006)

    def test_does_not_treat_proceeds_as_gross_offering_value(self):
        text = "Proceeds, before expenses, to us $20.15625 $562,500,006"
        self.assertIsNone(extract_authoritative_aggregate(text, expected_price=21.50))

    def test_requires_table_price_to_match_final_ipo_price(self):
        text = "Initial public offering price $ 21.50000 $ 600,000,006"
        self.assertIsNone(extract_authoritative_aggregate(text, expected_price=22.00))

    def test_preserves_authoritative_rounding_and_provenance(self):
        filing = {
            "company": "ERock, Inc.",
            "value": 600_000_005.5,
            "offering_size_source": "cover share title; explicit issuer-only cover statement matches total",
        }
        self.assertTrue(reconcile_record(filing, 600_000_006))
        self.assertEqual(filing["value"], 600_000_006)
        self.assertIn(SOURCE_MARKER, filing["offering_size_source"])

    def test_material_conflict_fails_closed(self):
        filing = {"company": "Bad Economics Co.", "value": 500_000_000}
        with self.assertRaises(OfferingValueReconciliationError):
            reconcile_record(filing, 600_000_000)

    def test_recent_priced_records_are_checked(self):
        filing = {
            "form": "424B4",
            "stage": "Priced",
            "pricing_date": "2026-08-20",
            "value": 100_000_000,
        }
        self.assertTrue(_needs_check(filing, today=date(2026, 8, 29)))

    def test_old_whole_dollar_records_are_not_refetched(self):
        filing = {
            "form": "424B4",
            "stage": "Priced",
            "pricing_date": "2026-06-01",
            "value": 100_000_000,
        }
        self.assertFalse(_needs_check(filing, today=date(2026, 8, 29)))

    def test_old_fractional_record_is_checked_for_rounding_repair(self):
        filing = {
            "form": "424B4",
            "stage": "Priced",
            "pricing_date": "2026-06-10",
            "value": 600_000_005.5,
        }
        self.assertTrue(_needs_check(filing, today=date(2026, 8, 29)))


if __name__ == "__main__":
    unittest.main()

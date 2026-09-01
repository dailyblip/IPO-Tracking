import unittest
from datetime import date

from offering_value_reconciler import (
    OfferingValueReconciliationError,
    PRIMARY_SHARES_MARKER,
    SOURCE_MARKER,
    _needs_check,
    extract_authoritative_aggregate,
    extract_authoritative_primary_shares,
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

    def test_extracts_scribe_explicit_issuer_primary_shares(self):
        text = """
        PROSPECTUS 8,580,000 Shares Common Stock.
        Scribe Therapeutics Inc. is offering 8,580,000 shares of its common stock.
        This is our initial public offering of shares of common stock, and no public
        market currently exists for our common stock. The initial public offering
        price is $15.00 per share.
        """
        self.assertEqual(extract_authoritative_primary_shares(text), 8_580_000)

    def test_does_not_treat_selling_stockholder_shares_as_primary(self):
        text = """
        PROSPECTUS. This is the initial public offering of Example Corp.
        The selling stockholders are offering 3,915,995 shares of our common stock.
        """
        self.assertIsNone(extract_authoritative_primary_shares(text))

    def test_primary_share_extraction_requires_ipo_context(self):
        text = "Example Corp. is offering 8,580,000 shares of its common stock under this shelf registration."
        self.assertIsNone(extract_authoritative_primary_shares(text))

    def test_preserves_authoritative_rounding_and_provenance(self):
        filing = {
            "company": "ERock, Inc.",
            "value": 600_000_005.5,
            "offering_size_source": "cover share title; explicit issuer-only cover statement matches total",
        }
        self.assertTrue(reconcile_record(filing, 600_000_006))
        self.assertEqual(filing["value"], 600_000_006)
        self.assertIn(SOURCE_MARKER, filing["offering_size_source"])

    def test_fills_blank_value_from_authoritative_sec_aggregate(self):
        filing = {
            "company": "Complete Economics Co.",
            "value": None,
            "offering_size_source": "",
        }
        self.assertTrue(reconcile_record(filing, 123_456_789))
        self.assertEqual(filing["value"], 123_456_789)
        self.assertIn(SOURCE_MARKER, filing["offering_size_source"])

    def test_repairs_blank_primary_shares_without_inventing_secondary_shares(self):
        filing = {
            "company": "Scribe Therapeutics, Inc.",
            "value": 128_700_000,
            "primary_offering_shares": None,
            "secondary_offering_shares": None,
            "offering_size_source": "authoritative final 424B4 aggregate IPO price table",
        }
        self.assertTrue(reconcile_record(filing, 128_700_000, primary_shares=8_580_000))
        self.assertEqual(filing["primary_offering_shares"], 8_580_000)
        self.assertIsNone(filing["secondary_offering_shares"])
        self.assertIn(PRIMARY_SHARES_MARKER, filing["offering_size_source"])

    def test_conflicting_explicit_primary_share_count_fails_closed(self):
        filing = {
            "company": "Conflict Co.",
            "value": 128_700_000,
            "primary_offering_shares": 7_000_000,
        }
        with self.assertRaises(OfferingValueReconciliationError):
            reconcile_record(filing, 128_700_000, primary_shares=8_580_000)

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

    def test_old_blank_value_is_checked_for_authoritative_recovery(self):
        filing = {
            "form": "424B4",
            "stage": "Priced",
            "pricing_date": "2026-06-01",
            "value": None,
        }
        self.assertTrue(_needs_check(filing, today=date(2026, 8, 29)))

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

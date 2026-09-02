import os
import unittest

os.environ.setdefault("SEC_EDGAR_USER_AGENT", "Research Monitor test@example.com")

import s1_preliminary_price_gate as gate


BITARI_COVER = (
    "PRELIMINARY PROSPECTUS SUBJECT TO COMPLETION. "
    "This is an initial public offering on a firm commitment basis of 4,285,715 shares "
    "of common stock of Bitari Inc. Prior to this offering, there has been no public "
    "market for our common stock. We expect the initial public offering price of the "
    "common stock to be $7.00 per share. We are offering the 4,285,715 shares of common "
    "stock in this offering."
)


class ProposedPointPriceRecoveryTests(unittest.TestCase):
    def test_expected_cover_point_price_is_authoritative(self):
        self.assertTrue(gate.has_authoritative_fixed_price(BITARI_COVER, 7.00))

    def test_blank_watch_terms_recover_from_explicit_sec_cover(self):
        filing = {
            "id": "0001185185-26-003678",
            "company": "Bitari Inc",
            "cik": "0002091680",
            "accession_no": "0001185185-26-003678",
            "form": "S-1",
            "stage": "Pre-pricing",
            "priority": "Medium",
            "price_range": None,
            "filing_price": None,
            "ipo_size": None,
            "offering_size_source": None,
            "offering_size_confidence": None,
            "primary_offering_shares": None,
            "secondary_offering_shares": None,
            "signals": [
                "Initial registration statement filed — IPO is pre-pricing",
                "No preliminary price range or fixed offering price detected yet",
            ],
            "sec_url": "https://www.sec.gov/test",
        }
        updated, invalid, checked = gate.review_watch_payload(
            {"filings": [filing]}, text_loader=lambda _: BITARI_COVER
        )
        result = updated["filings"][0]

        self.assertEqual(checked, 1)
        self.assertEqual(invalid, {})
        self.assertEqual(result["filing_price"], "$7.00")
        self.assertEqual(result["primary_offering_shares"], 4_285_715)
        self.assertEqual(result["ipo_size"], 30_000_005)
        self.assertEqual(result["offering_size_confidence"], "High")
        self.assertIn("issuer-only", result["offering_size_source"])
        self.assertIn(
            "Preliminary offering price disclosed at $7.00 per share",
            result["signals"],
        )
        self.assertNotIn(
            "No preliminary price range or fixed offering price detected yet",
            result["signals"],
        )

    def test_assumed_sensitivity_does_not_recover_blank_price(self):
        filing = {
            "id": "blank",
            "company": "Example Co.",
            "cik": "0000001234",
            "form": "S-1",
            "stage": "Pre-pricing",
            "filing_price": None,
            "price_range": None,
            "signals": ["No preliminary price range or fixed offering price detected yet"],
            "sec_url": "https://www.sec.gov/test",
        }
        sensitivity = (
            "This is an initial public offering. A $1.00 increase or decrease in the "
            "assumed initial public offering price of $7.00 per share would change net proceeds."
        )
        updated, invalid, checked = gate.review_watch_payload(
            {"filings": [filing]}, text_loader=lambda _: sensitivity
        )
        result = updated["filings"][0]

        self.assertEqual(checked, 0)
        self.assertEqual(invalid, {})
        self.assertIsNone(result["filing_price"])

    def test_queue_shape_recovers_value_label_without_guessing_secondary(self):
        filing = {
            "id": "s1:0002091680",
            "company": "Bitari Inc",
            "cik": "0002091680",
            "accession_no": "0001185185-26-003678",
            "form": "S-1",
            "stage": "Pre-pricing",
            "priority": "Medium",
            "price_range": None,
            "filing_price": None,
            "value": None,
            "value_label": "—",
            "offering_size_source": None,
            "offering_size_confidence": None,
            "primary_offering_shares": None,
            "secondary_offering_shares": None,
            "signals": ["No preliminary price range or fixed offering price detected yet"],
            "sec_url": "https://www.sec.gov/test",
        }
        updated, _, _ = gate.review_watch_payload(
            {"filings": [filing]}, text_loader=lambda _: BITARI_COVER
        )
        result = updated["filings"][0]

        self.assertEqual(result["value"], 30_000_005)
        self.assertEqual(result["value_label"], "$30,000,005")
        self.assertIsNone(result["secondary_offering_shares"])


if __name__ == "__main__":
    unittest.main()

import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("SEC_EDGAR_USER_AGENT", "Research Monitor test@example.com")

import s1_monitor


class AnySizeOperatingIpoTests(unittest.TestCase):
    def test_explicit_fixed_price_primary_terms_support_micro_ipo(self):
        terms = s1_monitor._explicit_fixed_price_primary_terms(
            "We are offering for sale a total of 6,000,000 shares of our common stock "
            "at a fixed price of $0.02 per share."
        )
        self.assertEqual(terms["shares"], 6_000_000)
        self.assertEqual(terms["price"], 0.02)
        self.assertEqual(terms["confidence"], "High")
        self.assertIn("primary offering", terms["source"].lower())

    def test_fixed_price_fallback_refuses_mixed_selling_holder_context(self):
        terms = s1_monitor._explicit_fixed_price_primary_terms(
            "We are offering for sale a total of 6,000,000 shares of common stock. "
            "Selling stockholders may offer additional shares. The shares are offered "
            "at a fixed price of $0.02 per share."
        )
        self.assertEqual(terms, {})

    @patch(
        "s1_monitor._is_micro_self_underwritten_offering",
        side_effect=AssertionError("legacy size gate must not run"),
    )
    @patch("s1_monitor.filing_parser.parse_filing")
    @patch("s1_monitor.filing_parser.fetch_document")
    @patch("s1_monitor.filing_parser.find_primary_document_url")
    @patch("s1_monitor.edgar_client.get_primary_ticker", return_value=None)
    @patch("s1_monitor.edgar_client.check_direct_listing_indicators", return_value=False)
    @patch("s1_monitor.edgar_client.check_spac_indicators", return_value=False)
    @patch("s1_monitor.edgar_client.is_first_time_registrant", return_value=True)
    @patch("s1_monitor.edgar_client.is_us_based", return_value=True)
    def test_micro_self_underwritten_operating_ipo_remains_eligible(
        self,
        us_based,
        first_time,
        spac,
        direct_listing,
        ticker,
        primary_doc,
        fetch_doc,
        parse_filing,
        legacy_gate,
    ):
        primary_doc.return_value = "https://sec.test/sensei-s1a.htm"
        soup = Mock()
        soup.get_text.return_value = (
            "Initial Public Offering. We are offering for sale a total of 6,000,000 "
            "shares of our common stock at a fixed price of $0.02 per share. "
            "This is a self-underwritten offering on a best-efforts basis."
        )
        fetch_doc.return_value = soup
        parse_filing.return_value = {
            "price_range": {"range_low": None, "range_high": None},
            "cover_page": {
                "exchange": None,
                "ticker": None,
                "offering_price": None,
                "offering_size_shares": None,
                "primary_offering_shares": None,
                "secondary_offering_shares": None,
                "offering_size_source": None,
                "offering_size_confidence": None,
                "offering_size_conflict": None,
            },
        }

        record = s1_monitor.enrich_record({
            "company_name": "Sensei Harbor Corp.",
            "cik": "2112634",
            "form_type": "S-1/A",
            "filing_date": "2026-08-18",
            "accession_no": "0001683168-26-006561",
        })

        self.assertIsNotNone(record)
        self.assertEqual(record["filing_price"], "$0.02")
        self.assertEqual(record["ipo_size"], 120_000)
        self.assertEqual(record["primary_offering_shares"], 6_000_000)
        self.assertEqual(record["offering_size_confidence"], "High")
        self.assertIn("primary offering", record["offering_size_source"].lower())
        self.assertIn("Fixed offering price disclosed at $0.02 per share", record["signals"])
        legacy_gate.assert_not_called()


if __name__ == "__main__":
    unittest.main()

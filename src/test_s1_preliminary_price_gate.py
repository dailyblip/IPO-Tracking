import os
import unittest

os.environ.setdefault("SEC_EDGAR_USER_AGENT", "Research Monitor test@example.com")

import s1_preliminary_price_gate as gate


class PreliminaryPriceGateTests(unittest.TestCase):
    def test_undetermined_terms_do_not_become_fixed_price(self):
        text = (
            "This is an initial public offering. The number of shares to be offered "
            "and the price range have not yet been determined. A strategic investor "
            "has committed $1.5 billion in a private placement at the IPO price."
        )
        self.assertFalse(gate.has_authoritative_fixed_price(text, 1.50))

    def test_scaled_aggregate_is_not_per_share_price(self):
        text = "Initial public offering price: $1.5 billion aggregate commitment."
        self.assertFalse(gate.has_authoritative_fixed_price(text, 1.50))

    def test_explicit_per_share_price_is_accepted(self):
        text = "The initial public offering price per share is $5.00."
        self.assertTrue(gate.has_authoritative_fixed_price(text, 5.00))

    def test_explicit_micro_fixed_price_is_accepted(self):
        text = (
            "This is our initial public offering. We are offering for sale "
            "6,000,000 shares at a fixed price of $0.02 per share."
        )
        self.assertTrue(gate.has_authoritative_fixed_price(text, 0.02))

    def test_review_clears_unsupported_price_and_derived_size(self):
        filing = {
            "id": "fixed",
            "company": "Example Energy, Inc.",
            "cik": "0002133037",
            "form": "S-1",
            "stage": "Pre-pricing",
            "filing_price": "$1.50",
            "price_range": None,
            "ipo_size": 1500000000,
            "offering_size_source": "SEC cover",
            "offering_size_confidence": "High",
            "priority": "High",
            "signals": [
                "Fixed offering price disclosed at $1.50 per share",
                "IPO size disclosed or derived at approximately $1,500,000,000",
            ],
            "sec_url": "https://www.sec.gov/test",
        }
        text = (
            "This is an initial public offering. The price range has not yet been "
            "determined. An investor has committed $1.5 billion at the IPO price."
        )
        updated, invalid, checked = gate.review_watch_payload(
            {"filings": [filing]}, text_loader=lambda _: text
        )
        result = updated["filings"][0]
        self.assertEqual(checked, 1)
        self.assertEqual(invalid, {"0002133037": "$1.50"})
        self.assertIsNone(result["filing_price"])
        self.assertIsNone(result["ipo_size"])
        self.assertIsNone(result["offering_size_source"])
        self.assertEqual(result["priority"], "Medium")
        self.assertIn(
            "No preliminary price range or fixed offering price detected yet",
            result["signals"],
        )

    def test_queue_record_is_cleared_for_same_cik(self):
        payload = {"filings": [{
            "id": "s1:0002133037",
            "company": "Example Energy, Inc.",
            "cik": "0002133037",
            "form": "S-1",
            "stage": "Pre-pricing",
            "filing_price": "$1.50",
            "price_range": None,
            "value": 1500000000,
            "value_label": "$1,500,000,000",
            "priority": "High",
            "signals": ["Fixed offering price disclosed at $1.50 per share"],
        }]}
        result = gate.sanitize_queue_payload(payload, {"0002133037": "$1.50"})["filings"][0]
        self.assertIsNone(result["filing_price"])
        self.assertIsNone(result["value"])
        self.assertEqual(result["value_label"], "—")
        self.assertEqual(result["priority"], "Medium")

    def test_sec_failure_fails_closed(self):
        filing = {
            "id": "fixed",
            "company": "Fixed Price Co.",
            "cik": "1234567",
            "form": "S-1",
            "stage": "Pre-pricing",
            "filing_price": "$5.00",
            "price_range": None,
            "sec_url": "https://www.sec.gov/test",
        }
        with self.assertRaises(gate.PreliminaryPriceGateError):
            gate.review_watch_payload(
                {"filings": [filing]},
                text_loader=lambda _: (_ for _ in ()).throw(RuntimeError("SEC unavailable")),
            )


if __name__ == "__main__":
    unittest.main()

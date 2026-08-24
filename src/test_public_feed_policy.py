import json
import tempfile
import unittest
from pathlib import Path

from public_feed_policy import MINIMUM_IPO_VALUE, enforce_public_feed_policy, qualifies_for_public_feed


class PublicFeedPolicyTests(unittest.TestCase):
    def test_threshold_is_inclusive_at_100m_for_priced_ipo(self):
        self.assertTrue(qualifies_for_public_feed({"company": "Large Operating Co", "form": "424B4", "value": MINIMUM_IPO_VALUE}))
        self.assertTrue(qualifies_for_public_feed({"company": "Large Operating Co", "form": "424B4", "value": "$100,000,000"}))

    def test_sub_100m_is_excluded(self):
        self.assertFalse(qualifies_for_public_feed({"company": "Small Operating Co", "form": "424B4", "value": 99_999_999}))
        self.assertFalse(qualifies_for_public_feed({"company": "Small Operating Co", "form": "424B4", "value": "99999999"}))

    def test_unknown_or_invalid_size_is_excluded(self):
        for value in (None, "", "unknown", float("nan"), float("inf"), True):
            self.assertFalse(qualifies_for_public_feed({"company": "Operating Co", "form": "424B4", "value": value}))

    def test_obvious_spac_and_investment_product_names_are_excluded_at_release(self):
        excluded = [
            "Gores Holdings XII, Inc.",
            "GigCapital10, Inc.",
            "Example Acquisition Corp.",
            "Example ETF Trust",
            "Example ETN Notes",
            "Example Exchange-Traded Fund",
        ]
        for company in excluded:
            with self.subTest(company=company):
                self.assertFalse(qualifies_for_public_feed({"company": company, "form": "424B4", "value": 500_000_000}))

    def test_legitimate_holdings_name_is_not_excluded_by_release_name_gate(self):
        self.assertTrue(
            qualifies_for_public_feed({"company": "Acme Holdings, Inc.", "form": "424B4", "value": 250_000_000})
        )

    def test_s1_fixed_price_size_without_issuer_provenance_is_excluded(self):
        filing = {
            "company": "Aura Consolidated Group, Inc.",
            "form": "S-1",
            "value": 478_548_213,
            "filing_price": "$3.34",
            "price_range": None,
        }
        self.assertFalse(qualifies_for_public_feed(filing))

    def test_s1_preliminary_range_can_qualify_at_threshold(self):
        filing = {
            "company": "Acme Robotics, Inc.",
            "form": "S-1/A",
            "value": 150_000_000,
            "price_range": "$18.00–$20.00",
        }
        self.assertTrue(qualifies_for_public_feed(filing))

    def test_s1_fixed_price_requires_high_confidence_issuer_source(self):
        safe = {
            "company": "Acme Robotics, Inc.",
            "form": "S-1",
            "value": 125_000_000,
            "filing_price": "$10.00",
            "offering_size_source": "explicit issuer-only cover statement",
            "offering_size_confidence": "High",
        }
        weak = dict(safe, offering_size_confidence="Medium")
        resale = dict(safe, offering_size_source="selling stockholder cover statement")
        generic_cover = dict(safe, offering_size_source="cover statement")
        self.assertTrue(qualifies_for_public_feed(safe))
        self.assertFalse(qualifies_for_public_feed(weak))
        self.assertFalse(qualifies_for_public_feed(resale))
        self.assertFalse(qualifies_for_public_feed(generic_cover))

    def test_policy_removes_non_qualifying_records_and_keeps_csv_in_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "generated_at": "2026-08-24T00:00:00+00:00",
                "source": "SEC EDGAR",
                "filings": [
                    {"id": "keep", "company": "Large IPO", "form": "424B4", "value": 125_000_000, "people": []},
                    {"id": "small", "company": "Small IPO", "form": "424B4", "value": 80_000_000, "people": []},
                    {"id": "unknown", "company": "Unknown IPO", "form": "424B4", "value": None, "people": []},
                    {"id": "spac", "company": "Gores Holdings XII, Inc.", "form": "424B4", "value": 600_000_000, "people": []},
                    {"id": "etf", "company": "Example ETF Trust", "form": "424B4", "value": 300_000_000, "people": []},
                    {"id": "resale", "company": "Aura Consolidated Group, Inc.", "form": "S-1", "value": 478_548_213, "filing_price": "$3.34", "people": []},
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")

            filtered, removed = enforce_public_feed_policy(output)

            self.assertEqual(removed, 5)
            self.assertEqual([filing["id"] for filing in filtered["filings"]], ["keep"])
            self.assertEqual(
                [filing["id"] for filing in json.loads(output.read_text(encoding="utf-8"))["filings"]],
                ["keep"],
            )
            csv_text = output.with_suffix(".csv").read_text(encoding="utf-8")
            self.assertIn("Large IPO", csv_text)
            self.assertNotIn("Small IPO", csv_text)
            self.assertNotIn("Unknown IPO", csv_text)
            self.assertNotIn("Gores Holdings XII", csv_text)
            self.assertNotIn("Example ETF Trust", csv_text)
            self.assertNotIn("Aura Consolidated Group", csv_text)


if __name__ == "__main__":
    unittest.main()

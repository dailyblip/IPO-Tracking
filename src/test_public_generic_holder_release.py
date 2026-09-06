"""Regression coverage for aggregate selling-holder labels in public owner lists."""

from __future__ import annotations

import unittest

from public_feed_policy import _remove_document_heading_people


class PublicGenericHolderReleaseTests(unittest.TestCase):
    def test_release_gate_removes_aggregate_seller_label_without_broad_name_filtering(self):
        filing = {
            "people_count": 3,
            "signals": [
                "3 named beneficial owners disclosed",
                "Offering raised approximately $100M",
            ],
            "people": [
                {
                    "name": "Other selling stockholders",
                    "shares": 980_735,
                    "cash_value": 12_425_912.45,
                    "cash_realized_ipo": 1_906_957.5,
                    "stanford_affiliated": True,
                },
                {"name": "Jane Q. Holder", "shares": 2_000_000},
                {"name": "Other Selling Stockholders Partners LLC", "shares": 500_000},
            ],
        }

        sanitized = _remove_document_heading_people(filing)

        self.assertEqual(
            [person["name"] for person in sanitized["people"]],
            ["Jane Q. Holder", "Other Selling Stockholders Partners LLC"],
        )
        self.assertEqual(sanitized["people_count"], 2)
        self.assertIn("2 named beneficial owners disclosed", sanitized["signals"])
        self.assertNotIn("3 named beneficial owners disclosed", sanitized["signals"])


if __name__ == "__main__":
    unittest.main()

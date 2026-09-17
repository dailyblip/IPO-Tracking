"""Regression coverage for stale exact Other ownership rows at public release."""

from __future__ import annotations

import unittest

from public_feed_policy import _remove_document_heading_people


class PublicOtherHolderReleaseTests(unittest.TestCase):
    def test_release_gate_removes_exact_other_but_preserves_real_entity_name(self):
        filing = {
            "people_count": 3,
            "signals": ["3 named beneficial owners disclosed"],
            "people": [
                {"name": "Other", "shares": 125_000},
                {"name": "Other World Capital LLC", "shares": 500_000},
                {"name": "Jane Q. Holder", "shares": 2_000_000},
            ],
        }

        sanitized = _remove_document_heading_people(filing)

        self.assertEqual(
            [person["name"] for person in sanitized["people"]],
            ["Other World Capital LLC", "Jane Q. Holder"],
        )
        self.assertEqual(sanitized["people_count"], 2)
        self.assertIn("2 named beneficial owners disclosed", sanitized["signals"])
        self.assertNotIn("3 named beneficial owners disclosed", sanitized["signals"])


if __name__ == "__main__":
    unittest.main()

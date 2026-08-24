import json
import tempfile
import unittest
from pathlib import Path

from public_feed_policy import MINIMUM_IPO_VALUE, enforce_public_feed_policy, qualifies_for_public_feed


class PublicFeedPolicyTests(unittest.TestCase):
    def test_threshold_is_inclusive_at_100m(self):
        self.assertTrue(qualifies_for_public_feed({"value": MINIMUM_IPO_VALUE}))
        self.assertTrue(qualifies_for_public_feed({"value": "$100,000,000"}))

    def test_sub_100m_is_excluded(self):
        self.assertFalse(qualifies_for_public_feed({"value": 99_999_999}))
        self.assertFalse(qualifies_for_public_feed({"value": "99999999"}))

    def test_unknown_or_invalid_size_is_excluded(self):
        for value in (None, "", "unknown", float("nan"), float("inf"), True):
            self.assertFalse(qualifies_for_public_feed({"value": value}))

    def test_policy_removes_non_qualifying_records_and_keeps_csv_in_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "generated_at": "2026-08-24T00:00:00+00:00",
                "source": "SEC EDGAR",
                "filings": [
                    {"id": "keep", "company": "Large IPO", "value": 125_000_000, "people": []},
                    {"id": "small", "company": "Small IPO", "value": 80_000_000, "people": []},
                    {"id": "unknown", "company": "Unknown IPO", "value": None, "people": []},
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")

            filtered, removed = enforce_public_feed_policy(output)

            self.assertEqual(removed, 2)
            self.assertEqual([filing["id"] for filing in filtered["filings"]], ["keep"])
            self.assertEqual(
                [filing["id"] for filing in json.loads(output.read_text(encoding="utf-8"))["filings"]],
                ["keep"],
            )
            csv_text = output.with_suffix(".csv").read_text(encoding="utf-8")
            self.assertIn("Large IPO", csv_text)
            self.assertNotIn("Small IPO", csv_text)
            self.assertNotIn("Unknown IPO", csv_text)


if __name__ == "__main__":
    unittest.main()

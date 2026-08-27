import json
import tempfile
import unittest
from pathlib import Path

from public_feed_policy import enforce_public_feed_policy


class PublicOwnerHeadingReleaseTests(unittest.TestCase):
    def test_release_gate_removes_stale_document_headings_and_syncs_owner_count(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "filings": [
                    {
                        "id": "csquare",
                        "company": "Csquare, Inc.",
                        "form": "424B4",
                        "filed": "2026-07-16",
                        "value": 441_000_000,
                        "people_count": 4,
                        "signals": [
                            "4 named beneficial owners disclosed",
                            "Offering raised approximately $441M",
                        ],
                        "people": [
                            {"name": "DESCRIPTION OF CAPITAL STOCK", "shares": 123},
                            {"name": "UNDERWRITING (CONFLICTS OF INTEREST)", "shares": 185},
                            {"name": "UNDERWRITING CAPITAL PARTNERS LLC", "shares": 2_000_000},
                            {"name": "Jane Founder", "shares": 1_000_000},
                        ],
                    }
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")

            filtered, removed_filings = enforce_public_feed_policy(output)

            self.assertEqual(removed_filings, 0)
            filing = filtered["filings"][0]
            self.assertEqual(
                [person["name"] for person in filing["people"]],
                ["UNDERWRITING CAPITAL PARTNERS LLC", "Jane Founder"],
            )
            self.assertEqual(filing["people_count"], 2)
            self.assertIn("2 named beneficial owners disclosed", filing["signals"])
            self.assertNotIn("4 named beneficial owners disclosed", filing["signals"])

            persisted = json.loads(output.read_text(encoding="utf-8"))
            persisted_filing = persisted["filings"][0]
            self.assertEqual(persisted_filing["people_count"], 2)
            self.assertNotIn(
                "DESCRIPTION OF CAPITAL STOCK",
                [person["name"] for person in persisted_filing["people"]],
            )
            self.assertNotIn(
                "UNDERWRITING (CONFLICTS OF INTEREST)",
                [person["name"] for person in persisted_filing["people"]],
            )


if __name__ == "__main__":
    unittest.main()

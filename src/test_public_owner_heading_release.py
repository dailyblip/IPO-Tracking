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
                        "id": "liftoff",
                        "company": "Liftoff Mobile, Inc.",
                        "form": "424B4",
                        "filed": "2026-06-04",
                        "value": 65_550_000,
                        "people_count": 8,
                        "signals": [
                            "8 named beneficial owners disclosed",
                            "Offering raised approximately $66M",
                        ],
                        "people": [
                            {"name": "DESCRIPTION OF CAPITAL STOCK", "shares": 123},
                            {"name": "UNDERWRITING (CONFLICTS OF INTEREST)", "shares": 185},
                            {"name": "Controlled company", "ownership_percent_after": 50.4},
                            {"name": "Conflicts of Interest", "ownership_percent_after": 10.0},
                            {"name": "UNDERWRITING CAPITAL PARTNERS LLC", "shares": 2_000_000},
                            {"name": "Jane Founder", "shares": 1_000_000},
                            {"name": "Controlled Company Partners LLC", "shares": 500_000},
                            {"name": "Conflicts of Interest Capital LLC", "shares": 250_000},
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
                [
                    "UNDERWRITING CAPITAL PARTNERS LLC",
                    "Jane Founder",
                    "Controlled Company Partners LLC",
                    "Conflicts of Interest Capital LLC",
                ],
            )
            self.assertEqual(filing["people_count"], 4)
            self.assertIn("4 named beneficial owners disclosed", filing["signals"])
            self.assertNotIn("8 named beneficial owners disclosed", filing["signals"])

            persisted = json.loads(output.read_text(encoding="utf-8"))
            persisted_filing = persisted["filings"][0]
            self.assertEqual(persisted_filing["people_count"], 4)
            for heading in (
                "DESCRIPTION OF CAPITAL STOCK",
                "UNDERWRITING (CONFLICTS OF INTEREST)",
                "Controlled company",
                "Conflicts of Interest",
            ):
                with self.subTest(heading=heading):
                    self.assertNotIn(
                        heading,
                        [person["name"] for person in persisted_filing["people"]],
                    )


if __name__ == "__main__":
    unittest.main()

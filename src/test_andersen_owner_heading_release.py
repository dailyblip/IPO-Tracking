import json
import tempfile
import unittest
from pathlib import Path

from ownership_parser import looks_like_document_heading
from public_feed_policy import enforce_public_feed_policy


class AndersenOwnerHeadingReleaseTests(unittest.TestCase):
    def test_tax_considerations_for_non_us_holders_is_document_heading(self):
        heading = "MATERIAL U.S. FEDERAL INCOME TAX CONSIDERATIONS FOR NON-U.S. HOLDERS"
        self.assertTrue(looks_like_document_heading(heading))
        self.assertFalse(looks_like_document_heading("Federal Income Tax Considerations Capital LLC"))

    def test_release_gate_removes_andersen_tax_heading(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "filings": [
                    {
                        "id": "andersen",
                        "company": "Andersen Group Inc.",
                        "form": "424B4",
                        "filed": "2026-08-13",
                        "value": 180_000_000,
                        "people_count": 2,
                        "signals": ["2 named beneficial owners disclosed"],
                        "people": [
                            {
                                "name": "MATERIAL U.S. FEDERAL INCOME TAX CONSIDERATIONS FOR NON-U.S. HOLDERS",
                                "shares": 171,
                            },
                            {"name": "Andersen Holdings LLC", "shares": 1_000_000},
                        ],
                    }
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")

            filtered, removed = enforce_public_feed_policy(output)

            self.assertEqual(removed, 0)
            filing = filtered["filings"][0]
            self.assertEqual([person["name"] for person in filing["people"]], ["Andersen Holdings LLC"])
            self.assertEqual(filing["people_count"], 1)
            self.assertEqual(filing["signals"], ["1 named beneficial owners disclosed"])


if __name__ == "__main__":
    unittest.main()

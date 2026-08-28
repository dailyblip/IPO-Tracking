import json
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from ownership_parser import looks_like_document_heading, parse_ownership_table
from public_feed_policy import enforce_public_feed_policy


class DocumentHeadingCleanupTests(unittest.TestCase):
    def test_attovia_section_headings_are_not_beneficial_owners(self):
        html = """<table>
        <tr><th>Name of beneficial owner</th><th>Shares beneficially owned</th></tr>
        <tr><td>Frazier Life Sciences XI, L.P.</td><td>5,565,980</td></tr>
        <tr><td>MATERIAL U.S. FEDERAL INCOME TAX CONSEQUENCES TO NON-U.S. HOLDERS</td><td>210</td></tr>
        <tr><td>UNDERWRITERS</td><td>215</td></tr>
        <tr><td>WHERE YOU CAN FIND ADDITIONAL INFORMATION</td><td>225</td></tr>
        </table>"""
        rows = parse_ownership_table(BeautifulSoup(html, "lxml").find("table"))
        self.assertEqual([row["name"] for row in rows], ["Frazier Life Sciences XI, L.P."])

    def test_underwriters_exact_heading_does_not_block_real_entity_name(self):
        self.assertTrue(looks_like_document_heading("UNDERWRITERS"))
        self.assertFalse(looks_like_document_heading("Underwriters Equity Partners LLC"))

    def test_release_gate_removes_stale_attovia_headings_and_syncs_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "filings": [
                    {
                        "id": "attovia",
                        "company": "Attovia Therapeutics, Inc.",
                        "form": "424B4",
                        "filed": "2026-08-05",
                        "value": 289_000_000,
                        "people_count": 4,
                        "signals": ["4 named beneficial owners disclosed"],
                        "people": [
                            {"name": "Material U.S. Federal Income Tax Consequences to Non-U.S. Holders", "shares": 210},
                            {"name": "Underwriters", "shares": 215},
                            {"name": "Where You Can Find Additional Information", "shares": 225},
                            {"name": "Frazier Life Sciences XI, L.P.", "shares": 5_565_980},
                        ],
                    }
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")

            filtered, removed = enforce_public_feed_policy(
                output,
                followon_submissions_loader=lambda _cik: {},
            )

            self.assertEqual(removed, 0)
            filing = filtered["filings"][0]
            self.assertEqual([person["name"] for person in filing["people"]], ["Frazier Life Sciences XI, L.P."])
            self.assertEqual(filing["people_count"], 1)
            self.assertEqual(filing["signals"], ["1 named beneficial owners disclosed"])

            persisted = output.read_text(encoding="utf-8")
            csv_text = output.with_suffix(".csv").read_text(encoding="utf-8")
            for heading in (
                "Material U.S. Federal Income Tax Consequences to Non-U.S. Holders",
                "Underwriters",
                "Where You Can Find Additional Information",
            ):
                self.assertNotIn(heading, persisted)
                self.assertNotIn(heading, csv_text)
            self.assertIn("Frazier Life Sciences XI, L.P.", csv_text)


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from stanford_sec_backfill import (
    _needs_sec_note_upgrade,
    enrich_feed,
    find_sec_stanford_affiliation,
    find_sec_stanford_evidence,
)


class StanfordSecBackfillTests(unittest.TestCase):
    def test_confirms_exact_beneficial_owner_from_management_bio(self):
        text = (
            "MANAGEMENT Executive Officers and Directors Wayne Ting 42 Chief Executive Officer "
            "Joseph Kraus 54 President Ann Gugino 53 Chief Financial Officer. "
            "Wayne Ting has served as our Chief Executive Officer since May 2020. "
            "Joseph Kraus has served as our President since November 2018. "
            "Mr. Kraus holds a B.A. in Political Science from Stanford University. "
            "Ann Gugino has served as our Chief Financial Officer since December 2023."
        )
        self.assertTrue(
            find_sec_stanford_affiliation(
                text,
                "Joseph Kraus(2)",
                ["Wayne Ting", "Joseph Kraus(2)", "Ann Gugino"],
            )
        )
        self.assertEqual(
            find_sec_stanford_evidence(
                text,
                "Joseph Kraus(2)",
                ["Wayne Ting", "Joseph Kraus(2)", "Ann Gugino"],
            ),
            "SEC 424B4 management biography confirms a degree from Stanford University.",
        )

    def test_does_not_assign_neighboring_persons_stanford_credential(self):
        text = (
            "Wayne Ting has served as our Chief Executive Officer since May 2020. "
            "Joseph Kraus has served as our President since November 2018. "
            "Mr. Kraus holds a B.A. in Political Science from Stanford University."
        )
        self.assertFalse(
            find_sec_stanford_affiliation(
                text,
                "Wayne Ting",
                ["Wayne Ting", "Joseph Kraus"],
            )
        )

    def test_requires_explicit_affiliation_language(self):
        text = (
            "Joseph Kraus has served as our President since November 2018. "
            "The company participates in programs near Stanford University."
        )
        self.assertFalse(find_sec_stanford_affiliation(text, "Joseph Kraus", ["Joseph Kraus"]))

    def test_requires_full_person_name(self):
        text = "Mr. Kraus holds a B.A. in Political Science from Stanford University."
        self.assertFalse(find_sec_stanford_affiliation(text, "Joseph Kraus", ["Joseph Kraus"]))

    def test_existing_sec_confirmation_is_rechecked_for_confidence_note_upgrade(self):
        self.assertTrue(_needs_sec_note_upgrade({
            "stanford_university_bio": True,
            "stanford_source": "SEC 424B4 management biography — https://www.sec.gov/example",
        }))
        self.assertFalse(_needs_sec_note_upgrade({
            "stanford_university_bio": True,
            "stanford_source": "Confidence 5/5 — SEC 424B4 management biography confirms a degree from Stanford University.",
        }))

    def test_enrich_feed_rewrites_legacy_sec_confirmation_with_note_and_provenance(self):
        payload = {
            "schema_version": 1,
            "filings": [
                {
                    "company": "Neutron Holdings, Inc.",
                    "form": "424B4",
                    "filed": "2026-07-31",
                    "sec_url": "https://www.sec.gov/Archives/edgar/data/1699963/index.html",
                    "people": [
                        {
                            "name": "Joseph Kraus",
                            "holder_type": "Person",
                            "shares": 507570,
                            "stanford_university_bio": True,
                            "stanford_source": (
                                "SEC 424B4 management biography — "
                                "https://www.sec.gov/Archives/edgar/data/1699963/legacy.htm"
                            ),
                        }
                    ],
                }
            ],
        }
        document_url = (
            "https://www.sec.gov/Archives/edgar/data/1699963/"
            "000162828026046635/neutronholdingsinc-424b4.htm"
        )
        soup = Mock()
        soup.get_text.return_value = (
            "Joseph Kraus has served as our President since November 2018. "
            "Mr. Kraus holds a B.A. in Political Science from Stanford University."
        )

        with tempfile.TemporaryDirectory() as directory:
            feed_path = Path(directory) / "filings.json"
            feed_path.write_text(json.dumps(payload), encoding="utf-8")
            with (
                patch(
                    "stanford_sec_backfill.filing_parser.find_primary_document_url",
                    return_value=document_url,
                ),
                patch("stanford_sec_backfill.filing_parser.fetch_document", return_value=soup),
                patch("stanford_sec_backfill.dashboard_export.write_dashboard_csv") as write_csv,
            ):
                result = enrich_feed(feed_path, start_date="2026-06-01")

            refreshed = json.loads(feed_path.read_text(encoding="utf-8"))
            person = refreshed["filings"][0]["people"][0]
            self.assertEqual(result["confirmed_people"], 1)
            self.assertTrue(person["stanford_university_bio"])
            self.assertTrue(person["stanford_source"].startswith("Confidence 5/5 — "))
            self.assertIn(
                "SEC 424B4 management biography confirms a degree from Stanford University.",
                person["stanford_source"],
            )
            self.assertIn(f"Source: {document_url}", person["stanford_source"])
            write_csv.assert_called_once()


if __name__ == "__main__":
    unittest.main()

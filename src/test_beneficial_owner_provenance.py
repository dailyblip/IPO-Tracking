import unittest
from pathlib import Path

import dashboard_export
from prospect_research import prospect_person_metadata
from feed_schema_contract import load_schema


ROOT = Path(__file__).resolve().parents[1]


class BeneficialOwnerProvenanceTests(unittest.TestCase):
    def _row(self, beneficial_owner):
        return {
  "_accession_no": "0001234567-26-000001",
  "_cik": "1234567",
  "_form": "424B4",
  "_sec_url": "https://www.sec.gov/Archives/edgar/data/1234567/000123456726000001/0001234567-26-000001-index.htm",
  "Company Name": "Owner Provenance Co.",
  "Ticker": "OWNR",
  "Date of Filing": "2026-08-01",
  "Date of Pricing": "2026-08-05",
  "Actual Price": 10.0,
  "Amount Raised": 10000000.0,
  "Offering Size Source": "authoritative final 424B4 terms",
  "Offering Size Confidence": "High",
  "Holder Name": "Confirmed Stanford Person",
  "Beneficial Owner": beneficial_owner,
  "Shares": None,
  "Shares After IPO": None,
  "Stanford Grade": 5,
  "Stanford Affiliation Confirmed": True,
  "Stanford University in Bio": True,
  "Stanford Justification": "SEC filing confirms the Stanford affiliation.",
        }

    def test_metadata_preserves_owner_provenance_independently_of_share_count(self):
        metadata = prospect_person_metadata(self._row(True), "Confirmed Stanford Person")
        self.assertTrue(metadata["is_beneficial_owner"])
        self.assertTrue(metadata["stanford_university_bio"])

    def test_management_only_person_is_not_promoted_to_beneficial_owner(self):
        metadata = prospect_person_metadata(self._row(False), "Confirmed Stanford Person")
        self.assertFalse(metadata["is_beneficial_owner"])
        self.assertTrue(metadata["stanford_university_bio"])

    def test_public_payload_keeps_owner_flag_when_shares_are_unavailable(self):
        payload = dashboard_export.build_payload(
  [self._row(True)], generated_at="2026-09-03T00:00:00+00:00"
        )
        person = payload["filings"][0]["people"][0]
        self.assertTrue(person["is_beneficial_owner"])
        self.assertIsNone(person["shares"])

    def test_pipeline_marks_parsed_holders_and_management_separately(self):
        source = (ROOT / "src" / "main.py").read_text(encoding="utf-8")
        self.assertIn('"Beneficial Owner": bool(holder_name)', source)
        self.assertIn('"Beneficial Owner": False', source)

    def test_dashboard_uses_owner_provenance_not_share_quantity_for_stanford_red(self):
        html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn(
  'function isStanfordBeneficialOwner(person){return person.stanford_university_bio===true&&person.is_beneficial_owner===true}',
  html,
        )
        self.assertNotIn(
  'person.stanford_university_bio===true&&Number.isFinite(shares)&&shares>0',
  html,
        )

    def test_v1_schema_and_allowlist_carry_owner_provenance(self):
        schema = load_schema(dashboard_export.SCHEMA_VERSION)
        self.assertIn("is_beneficial_owner", dashboard_export.PUBLIC_PERSON_FIELDS)
        self.assertIn("is_beneficial_owner", schema["$defs"]["person"]["properties"])


if __name__ == "__main__":
    unittest.main()

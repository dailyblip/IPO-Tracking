import json
import tempfile
import unittest
from pathlib import Path

from dashboard_export import build_payload, export_dashboard


def sample_row(**overrides):
    row = {
        "Company Name": "Acme Robotics",
        "Ticker": "ACME",
        "Date of Filing": "2026-08-01",
        "Date of Pricing": "2026-08-15",
        "Amount Raised": 600_000_000,
        "Holder Name": "Jane Founder",
        "Shares": 2_000_000,
        "Cash Value": 50_000_000,
        "Stanford Grade": 5,
        "Stanford Justification": "Direct degree evidence.",
        "Lock-Up Expiry": "180 days after the offering",
        "QC Status": "Verified",
        "QC Notes": "",
        "_cik": "1234567",
        "_accession_no": "0001234567-26-000001",
        "_form": "424B4",
        "_sec_url": "https://www.sec.gov/example",
    }
    row.update(overrides)
    return row


class DashboardExportTests(unittest.TestCase):
    def test_build_payload_groups_people_and_prioritizes(self):
        payload = build_payload([
            sample_row(),
            sample_row(**{"Holder Name": "John Investor", "Stanford Grade": 0}),
        ], generated_at="2026-08-17T00:00:00+00:00")
        filing = payload["filings"][0]
        self.assertEqual(filing["company"], "Acme Robotics")
        self.assertEqual(filing["people_count"], 2)
        self.assertEqual(filing["priority"], "High")
        self.assertEqual(filing["value_label"], "$600M")
        self.assertEqual(filing["cik"], "0001234567")
        serialized = json.dumps(filing)
        self.assertNotIn("stanford_grade", serialized)
        self.assertNotIn("affiliation_evidence", serialized)
        self.assertNotIn("qc_status", serialized)
        self.assertNotIn("qc_notes", serialized)

    def test_export_merges_existing_history(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            old = build_payload([sample_row(**{
                "Company Name": "Older Co", "Ticker": "OLD", "Date of Pricing": "2026-07-01",
                "_accession_no": "old-accession",
            })])
            old["filings"][0]["internal_note"] = "must not publish"
            old["filings"][0]["people"][0]["qc_notes"] = "must not publish"
            output.write_text(json.dumps(old), encoding="utf-8")
            exported = export_dashboard([sample_row()], output)
            self.assertEqual(
                {f["id"] for f in exported["filings"]},
                {"old-accession", "0001234567-26-000001"},
            )
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["schema_version"], 1)
            serialized = json.dumps(exported)
            self.assertNotIn("internal_note", serialized)
            self.assertNotIn("must not publish", serialized)

    def test_normalizes_public_labels_and_excludes_aggregate_rows(self):
        payload = build_payload([
            sample_row(**{
                "Company Name": "Acme Robotics (CIK 0001234567)",
                "Holder Name": "Jane Founder (1)(2)",
                "Amount Raised": None,
                "_form": None,
            }),
            sample_row(**{
                "Company Name": "Acme Robotics (CIK 0001234567)",
                "Holder Name": "All current directors and executive officers as a group (12 persons)",
                "Amount Raised": None,
                "Cash Value": 900_000_000,
                "_form": None,
            }),
        ])
        filing = payload["filings"][0]
        self.assertEqual(filing["company"], "Acme Robotics")
        self.assertEqual(filing["form"], "424B4")
        self.assertEqual(filing["value_label"], "—")
        self.assertEqual(filing["people_count"], 1)
        self.assertEqual(filing["people"][0]["name"], "Jane Founder")
        self.assertNotIn("All current directors", json.dumps(filing))


    def test_keeps_filing_when_no_owner_rows_are_available(self):
        payload = build_payload([
            sample_row(**{
                "Company Name": "Acme Robotics  (ACME)",
                "Holder Name": "",
                "Shares": None,
                "Cash Value": None,
            })
        ])
        filing = payload["filings"][0]
        self.assertEqual(filing["company"], "Acme Robotics")
        self.assertEqual(filing["people_count"], 0)
        self.assertEqual(filing["people"], [])
        self.assertIn("Final prospectus available for researcher review", filing["signals"])


if __name__ == "__main__":
    unittest.main()

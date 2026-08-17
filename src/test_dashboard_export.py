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

    def test_export_merges_existing_history(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            old = build_payload([sample_row(**{
                "Company Name": "Older Co", "Ticker": "OLD", "Date of Pricing": "2026-07-01",
                "_accession_no": "old-accession",
            })])
            output.write_text(json.dumps(old), encoding="utf-8")
            exported = export_dashboard([sample_row()], output)
            self.assertEqual(
                {f["id"] for f in exported["filings"]},
                {"old-accession", "0001234567-26-000001"},
            )
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from dashboard_export import build_payload, export_dashboard, refresh_market_prices


def sample_row(**overrides):
    row = {
        "Company Name": "Acme Robotics",
        "Ticker": "ACME",
        "Date of Filing": "2026-08-01",
        "Date of Pricing": "2026-08-15",
        "Filing Price": "18.00-20.00",
        "Actual Price": 20.00,
        "Amount Raised": 600_000_000,
        "Current Price": 24.50,
        "Holder Name": "Jane Founder",
        "Shares": 2_000_000,
        "Cash Value": 50_000_000,
        "Stanford Grade": 5,
        "Stanford Justification": "Direct degree evidence.",
        "Stanford University in Bio": True,
        "Lock-Up Expiry": "180 days after the offering",
        "QC Status": "Verified",
        "QC Notes": "",
        "Last Updated": "2026-08-17",
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
            sample_row(**{
                "Holder Name": "John Investor",
                "Stanford Grade": 0,
                "Stanford University in Bio": False,
            }),
        ], generated_at="2026-08-17T00:00:00+00:00")
        filing = payload["filings"][0]
        self.assertEqual(filing["company"], "Acme Robotics")
        self.assertEqual(filing["people_count"], 2)
        self.assertEqual(filing["priority"], "High")
        self.assertEqual(filing["value_label"], "$600M")
        self.assertEqual(filing["cik"], "0001234567")
        self.assertEqual(filing["filing_price"], "18.00-20.00")
        self.assertEqual(filing["offering_price"], 20.0)
        self.assertEqual(filing["current_price"], 24.5)
        self.assertEqual(filing["price_updated"], "2026-08-17")
        self.assertTrue(filing["people"][0]["stanford_university_bio"])
        self.assertFalse(filing["people"][1]["stanford_university_bio"])
        serialized = json.dumps(filing)
        self.assertNotIn("stanford_grade", serialized)
        self.assertNotIn("affiliation_evidence", serialized)
        self.assertNotIn("qc_status", serialized)
        self.assertNotIn("qc_notes", serialized)

    def test_refresh_market_prices_updates_quotes_and_holder_values(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            export_dashboard([sample_row()], output)

            payload = refresh_market_prices(
                output,
                {"ACME": 31.25},
                updated_at="2026-08-18",
            )

            filing = payload["filings"][0]
            self.assertEqual(filing["current_price"], 31.25)
            self.assertEqual(filing["price_updated"], "2026-08-18")
            self.assertEqual(filing["people"][0]["cash_value"], 62_500_000)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8"))["generated_at"],
                "2026-08-18",
            )

    def test_public_allowlist_preserves_s1_pricing_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            existing = build_payload([])
            existing["filings"] = [{
                "id": "s1:0001234567",
                "company": "Acme Robotics",
                "ticker": "ACME",
                "form": "S-1/A",
                "filed": "2026-08-17",
                "stage": "Pre-pricing",
                "price_range": "$18.00–$20.00",
                "people": [],
                "internal_note": "must not publish",
            }]
            output.write_text(json.dumps(existing), encoding="utf-8")

            exported = export_dashboard([], output)

            filing = exported["filings"][0]
            self.assertEqual(filing["stage"], "Pre-pricing")
            self.assertEqual(filing["price_range"], "$18.00–$20.00")
            self.assertNotIn("internal_note", filing)

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
                "Holder Name": "Jane \uFEFFFounder (1)(2)",
                "Amount Raised": None,
                "_form": None,
            }),
            sample_row(**{
                "Company Name": "Acme Robotics (CIK 0001234567)",
                "Holder Name": "Directors, director nominee and executive officers as a group (14 persons)",
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
        self.assertNotIn("director nominee", json.dumps(filing))


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


    def test_backfill_replaces_only_the_requested_date_range(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            old = build_payload([
                sample_row(**{
                    "Company Name": "Stale Direct Listing",
                    "Ticker": "STALE",
                    "Date of Pricing": "2026-07-29",
                    "_accession_no": "stale-accession",
                }),
                sample_row(**{
                    "Company Name": "Older IPO",
                    "Ticker": "OLD",
                    "Date of Pricing": "2026-06-15",
                    "_accession_no": "older-accession",
                }),
            ])
            output.write_text(json.dumps(old), encoding="utf-8")

            exported = export_dashboard(
                [sample_row(**{
                    "Company Name": "Corrected IPO",
                    "Ticker": "NEW",
                    "Date of Pricing": "2026-08-05",
                    "_accession_no": "corrected-accession",
                })],
                output,
                replace_start="2026-07-17",
                replace_end="2026-08-17",
            )

            self.assertEqual(
                {filing["id"] for filing in exported["filings"]},
                {"older-accession", "corrected-accession"},
            )


if __name__ == "__main__":
    unittest.main()

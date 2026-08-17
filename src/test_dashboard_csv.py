import csv
import json
import tempfile
import unittest
from pathlib import Path

import dashboard_export


class DashboardCsvExportTests(unittest.TestCase):
    def test_export_dashboard_writes_flattened_csv(self):
        rows = [
            {
                "Company Name": "Example, Inc.",
                "Ticker": "EXM",
                "Date of Pricing": "2026-08-17",
                "Amount Raised": 125_000_000,
                "Filing Price": "18.00-20.00",
                "Actual Price": 20.00,
                "Current Price": 24.50,
                "Holder Name": "Ada Example",
                "Shares": 1000,
                "Cash Value": 25_000,
                "Stanford University in Bio": True,
                "Last Updated": "2026-08-17",
                "_cik": "1234567",
                "_accession_no": "0001234567-26-000001",
                "_form": "424B4",
                "_sec_url": "https://www.sec.gov/example",
            },
            {
                "Company Name": "Example, Inc.",
                "Ticker": "EXM",
                "Date of Pricing": "2026-08-17",
                "Amount Raised": 125_000_000,
                "Filing Price": "18.00-20.00",
                "Actual Price": 20.00,
                "Current Price": 24.50,
                "Holder Name": "Grace Example",
                "Shares": 2000,
                "Cash Value": 50_000,
                "_cik": "1234567",
                "_accession_no": "0001234567-26-000001",
                "_form": "424B4",
                "_sec_url": "https://www.sec.gov/example",
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "filings.json"
            payload = dashboard_export.export_dashboard(rows, json_path)
            csv_path = Path(directory) / "filings.csv"

            self.assertTrue(json_path.exists())
            self.assertTrue(csv_path.exists())
            self.assertEqual(len(payload["filings"]), 1)

            with csv_path.open(encoding="utf-8", newline="") as handle:
                exported = list(csv.DictReader(handle))

            self.assertEqual(len(exported), 2)
            self.assertEqual(exported[0]["company"], "Example, Inc.")
            self.assertEqual(exported[0]["ticker"], "EXM")
            self.assertEqual(exported[0]["holder_name"], "Ada Example")
            self.assertEqual(exported[1]["holder_name"], "Grace Example")
            self.assertEqual(exported[0]["accession_no"], "0001234567-26-000001")
            self.assertEqual(exported[0]["sec_url"], "https://www.sec.gov/example")
            self.assertEqual(exported[0]["filing_price"], "18.00-20.00")
            self.assertEqual(exported[0]["offering_price"], "20.0")
            self.assertEqual(exported[0]["current_price"], "24.5")
            self.assertEqual(exported[0]["stanford_university_bio"], "True")

    def test_csv_preserves_filing_without_named_owner(self):
        rows = [{
            "Company Name": "No Owners Corp.",
            "Ticker": "NONE",
            "Date of Pricing": "2026-08-17",
            "Amount Raised": 20_000_000,
            "Holder Name": "",
            "Shares": None,
            "Cash Value": None,
            "_accession_no": "0000000000-26-000001",
        }]

        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "filings.json"
            dashboard_export.export_dashboard(rows, json_path)
            with (Path(directory) / "filings.csv").open(encoding="utf-8", newline="") as handle:
                exported = list(csv.DictReader(handle))

            self.assertEqual(len(exported), 1)
            self.assertEqual(exported[0]["company"], "No Owners Corp.")
            self.assertEqual(exported[0]["holder_name"], "")


if __name__ == "__main__":
    unittest.main()

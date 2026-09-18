import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from offering_value_reconciler import reconcile_feed, reconcile_record


class OfferingValueLabelSyncTests(unittest.TestCase):
    def test_reconciled_value_refreshes_derived_label(self):
        filing = {
            "company": "Example Co.",
            "value": None,
            "value_label": "—",
            "offering_size_source": "",
            "offering_size_confidence": "Unresolved",
        }

        self.assertTrue(reconcile_record(filing, 123_456_789))
        self.assertEqual(filing["value"], 123_456_789)
        self.assertEqual(filing["value_label"], "$123M")

    def test_old_whole_dollar_row_repairs_stale_label_without_sec_refetch(self):
        payload = {
            "schema_version": 1,
            "filings": [
                {
                    "id": "0001193125-26-224302",
                    "company": "EagleRock Land, LLC",
                    "accession_no": "0001193125-26-224302",
                    "form": "424B4",
                    "stage": "Priced",
                    "pricing_date": "2026-05-13",
                    "value": 320_050_000,
                    "value_label": "—",
                    "offering_size_source": "authoritative final 424B4 aggregate IPO price table",
                    "offering_size_confidence": "High",
                    "sec_url": "https://www.sec.gov/Archives/example-index.htm",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "filings.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            updates = reconcile_feed(path, today=date(2026, 9, 5))
            refreshed = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(updates, {})
        self.assertEqual(refreshed["filings"][0]["value"], 320_050_000)
        self.assertEqual(refreshed["filings"][0]["value_label"], "$320M")

    def test_invalid_populated_values_degrade_to_unknown_without_excluding_rows(self):
        invalid_values = ["unknown", True, 0, -5]
        payload = {
            "schema_version": 1,
            "filings": [
                {
                    "id": f"invalid-{index}",
                    "company": f"Operating Company {index}",
                    "form": "424B4",
                    "stage": "Priced",
                    "pricing_date": "2026-08-01",
                    "value": value,
                    "value_label": "$999M",
                    "sec_url": "",
                }
                for index, value in enumerate(invalid_values)
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "filings.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            updates = reconcile_feed(path, today=date(2026, 9, 5))
            refreshed = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(updates, {})
        self.assertEqual(len(refreshed["filings"]), len(invalid_values))
        for filing in refreshed["filings"]:
            self.assertIsNone(filing["value"])
            self.assertEqual(filing["value_label"], "—")

    def test_valid_sub_100m_value_remains_visible_and_is_not_raised_to_threshold(self):
        payload = {
            "schema_version": 1,
            "filings": [
                {
                    "id": "small-operating-ipo",
                    "company": "Small Operating Company",
                    "form": "424B4",
                    "stage": "Priced",
                    "pricing_date": "2026-08-01",
                    "value": 8_000_000,
                    "value_label": "stale",
                    "primary_offering_shares": 1_000_000,
                    "sec_url": "",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "filings.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            reconcile_feed(path, today=date(2026, 9, 5))
            refreshed = json.loads(path.read_text(encoding="utf-8"))

        filing = refreshed["filings"][0]
        self.assertEqual(filing["value"], 8_000_000)
        self.assertEqual(filing["value_label"], "$8M")


if __name__ == "__main__":
    unittest.main()

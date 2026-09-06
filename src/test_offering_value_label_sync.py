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


if __name__ == "__main__":
    unittest.main()

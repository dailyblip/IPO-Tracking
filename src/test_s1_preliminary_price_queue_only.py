import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SEC_EDGAR_USER_AGENT", "Research Monitor test@example.com")

import s1_preliminary_price_gate as gate


class QueueOnlyPreliminaryPriceGateTests(unittest.TestCase):
    def _filing(self, *, price="$1.50", accession="0000000000-26-000001"):
        return {
            "id": "s1:0002133037",
            "company": "Example Energy, Inc.",
            "cik": "0002133037",
            "accession_no": accession,
            "form": "S-1",
            "stage": "Pre-pricing",
            "filing_price": price,
            "price_range": None,
            "value": 1500000000,
            "value_label": "$1,500,000,000",
            "offering_size_source": "SEC cover",
            "offering_size_confidence": "High",
            "priority": "High",
            "signals": [
                f"Fixed offering price disclosed at {price} per share",
                "IPO size disclosed or derived at approximately $1,500,000,000",
            ],
            "sec_url": "https://www.sec.gov/test",
        }

    def test_enforce_reviews_fixed_price_present_only_in_public_queue(self):
        watch_payload = {"filings": []}
        queue_payload = {"filings": [self._filing()]}
        text = (
            "This is an initial public offering. The price range has not yet been "
            "determined. An investor has committed $1.5 billion at the IPO price."
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            watch_path = root / "s1_watch.json"
            queue_path = root / "filings.json"
            watch_path.write_text(json.dumps(watch_payload), encoding="utf-8")
            queue_path.write_text(json.dumps(queue_payload), encoding="utf-8")

            with patch.object(gate.dashboard_export, "write_dashboard_csv") as csv_writer:
                _, updated_queue, invalid, checked = gate.enforce_preliminary_fixed_prices(
                    watch_path,
                    queue_path,
                    text_loader=lambda _: text,
                )

        result = updated_queue["filings"][0]
        self.assertEqual(checked, 1)
        self.assertEqual(invalid, {"0002133037": "$1.50"})
        self.assertIsNone(result["filing_price"])
        self.assertIsNone(result["value"])
        self.assertEqual(result["value_label"], "—")
        self.assertIsNone(result["offering_size_source"])
        self.assertEqual(result["priority"], "Medium")
        self.assertIn(
            "No preliminary price range or fixed offering price detected yet",
            result["signals"],
        )
        csv_writer.assert_called_once()

    def test_same_exact_watch_and_queue_filing_is_verified_once(self):
        filing = self._filing(price="$5.00")
        watch_payload = {"filings": [filing]}
        queue_payload = {"filings": [dict(filing)]}
        calls = []

        def loader(_):
            calls.append(True)
            return "The initial public offering price per share is $5.00."

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            watch_path = root / "s1_watch.json"
            queue_path = root / "filings.json"
            watch_path.write_text(json.dumps(watch_payload), encoding="utf-8")
            queue_path.write_text(json.dumps(queue_payload), encoding="utf-8")

            with patch.object(gate.dashboard_export, "write_dashboard_csv") as csv_writer:
                _, updated_queue, invalid, checked = gate.enforce_preliminary_fixed_prices(
                    watch_path,
                    queue_path,
                    text_loader=loader,
                )

        self.assertEqual(checked, 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(invalid, {})
        self.assertEqual(updated_queue["filings"][0]["filing_price"], "$5.00")
        csv_writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()

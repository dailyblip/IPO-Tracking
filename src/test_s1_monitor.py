import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("SEC_EDGAR_USER_AGENT", "Research Monitor test@example.com")

import s1_monitor


class S1MonitorTests(unittest.TestCase):
    def test_parse_daily_index_keeps_s1_and_amendments_only(self):
        text = """Description
-----
1234567|Acme Robotics, Inc.|S-1|2026-08-17|edgar/data/1234567/0001234567-26-000001.txt
1234567|Acme Robotics, Inc.|S-1/A|2026-08-18|edgar/data/1234567/0001234567-26-000002.txt
7654321|Other Co|10-K|2026-08-17|edgar/data/7654321/0007654321-26-000003.txt
"""
        rows = s1_monitor.parse_daily_index(text)
        self.assertEqual([row["form_type"] for row in rows], ["S-1", "S-1/A"])
        self.assertEqual(rows[0]["accession_no"], "0001234567-26-000001")

    def test_format_range(self):
        self.assertEqual(s1_monitor._format_range("18", "20"), "$18.00–$20.00")
        self.assertIsNone(s1_monitor._format_range(None, "20"))

    @patch("s1_monitor.filing_parser.parse_filing")
    @patch("s1_monitor.filing_parser.fetch_document")
    @patch("s1_monitor.filing_parser.find_primary_document_url")
    @patch("s1_monitor.edgar_client.get_primary_ticker")
    @patch("s1_monitor.edgar_client.is_first_time_registrant", return_value=True)
    @patch("s1_monitor.edgar_client.is_us_based", return_value=True)
    def test_enrich_record_captures_preliminary_range(
        self, us_based, first_time, ticker, primary_doc, fetch_doc, parse_filing
    ):
        ticker.return_value = "ACME"
        primary_doc.return_value = "https://sec.test/acme-s1.htm"
        soup = Mock()
        soup.get_text.return_value = "This is the initial public offering of our common stock."
        fetch_doc.return_value = soup
        parse_filing.return_value = {"price_range": {"range_low": 18, "range_high": 20}}

        record = s1_monitor.enrich_record({
            "company_name": "Acme Robotics, Inc.",
            "cik": "1234567",
            "form_type": "S-1/A",
            "filing_date": "2026-08-17",
            "accession_no": "0001234567-26-000001",
        })

        self.assertEqual(record["ticker"], "ACME")
        self.assertEqual(record["price_range"], "$18.00–$20.00")
        self.assertEqual(record["priority"], "High")
        self.assertIn("Preliminary offering range disclosed", record["signals"][1])

    @patch("s1_monitor.edgar_client.is_us_based", return_value=False)
    def test_enrich_record_rejects_non_us_filer(self, us_based):
        record = s1_monitor.enrich_record({
            "company_name": "Foreign Issuer",
            "cik": "123",
            "form_type": "S-1",
            "filing_date": "2026-08-17",
            "accession_no": "0000000123-26-000001",
        })
        self.assertIsNone(record)

    def test_export_feed_merges_history_and_is_atomic(self):
        old = {
            "id": "old",
            "company": "Old Co",
            "filed": "2026-08-10",
            "form": "S-1",
        }
        new = {
            "id": "new",
            "company": "New Co",
            "filed": "2026-08-17",
            "form": "S-1/A",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s1_watch.json"
            path.write_text(json.dumps({"filings": [old]}), encoding="utf-8")
            payload = s1_monitor.export_feed([new], path)
            self.assertEqual([item["id"] for item in payload["filings"]], ["new", "old"])
            self.assertFalse(Path(str(path) + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()

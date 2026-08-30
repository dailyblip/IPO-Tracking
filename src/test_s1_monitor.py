import json
import csv
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

    def test_normalizes_compact_filing_date(self):
        self.assertEqual(s1_monitor._normalize_filing_date("20260818"), "2026-08-18")
        self.assertEqual(s1_monitor._normalize_filing_date("2026-08-18"), "2026-08-18")

    def test_does_not_use_registration_fee_aggregate_as_ipo_size(self):
        value = s1_monitor._extract_ipo_size(
            "Proposed Maximum Aggregate Offering Price $120,000", {}, {}
        )
        self.assertIsNone(value)

    def test_derives_fixed_price_offering_size_from_high_confidence_cover_terms(self):
        value = s1_monitor._extract_ipo_size(
            "Initial public offering",
            {
                "cover_page": {
                    "offering_size_shares": 6_000_000,
                    "offering_size_confidence": "High",
                    "offering_size_conflict": False,
                    "offering_price": 0.02,
                }
            },
            {},
        )
        self.assertEqual(value, 120_000)

    def test_does_not_derive_size_from_ambiguous_sale_of_shares_prose(self):
        value = s1_monitor._extract_ipo_size(
            "This prospectus also relates to the sale of 2,026 shares by a selling stockholder.",
            {"cover_page": {"offering_price": 5.50}},
            {},
        )
        self.assertIsNone(value)

    def test_micro_self_underwritten_registration_without_exchange_is_rejected(self):
        self.assertTrue(s1_monitor._is_micro_self_underwritten_offering(
            "The offering is being conducted on a self-underwritten, best-efforts basis.",
            {"cover_page": {"exchange": None}},
            120_000,
        ))
        self.assertFalse(s1_monitor._is_micro_self_underwritten_offering(
            "The offering is being conducted on a best-efforts basis.",
            {"cover_page": {"exchange": "Nasdaq"}},
            120_000,
        ))

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
        parse_filing.return_value = {"price_range": {"range_low": 18, "range_high": 20}, "cover_page": {"exchange": "Nasdaq", "offering_price": 19}}

        record = s1_monitor.enrich_record({
            "company_name": "Acme Robotics, Inc.",
            "cik": "1234567",
            "form_type": "S-1/A",
            "filing_date": "2026-08-17",
            "accession_no": "0001234567-26-000001",
        })

        self.assertEqual(record["ticker"], "ACME")
        self.assertEqual(record["price_range"], "$18.00–$20.00")
        self.assertEqual(record["filing_price"], "$18.00–$20.00")
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

    @patch("s1_monitor.edgar_client.is_us_based", side_effect=RuntimeError("SEC unavailable"))
    def test_evaluate_record_preserves_state_on_transient_failure(self, us_based):
        record, evaluated = s1_monitor.evaluate_record({
            "company_name": "Acme Robotics, Inc.",
            "cik": "1234567",
            "form_type": "S-1",
            "filing_date": "2026-08-17",
            "accession_no": "0001234567-26-000001",
        })
        self.assertIsNone(record)
        self.assertFalse(evaluated)

    @patch("s1_monitor.edgar_client.is_us_based", return_value=False)
    def test_evaluate_record_marks_deterministic_rejection_complete(self, us_based):
        record, evaluated = s1_monitor.evaluate_record({
            "company_name": "Foreign Issuer",
            "cik": "1234567",
            "form_type": "S-1",
            "filing_date": "2026-08-17",
            "accession_no": "0001234567-26-000001",
        })
        self.assertIsNone(record)
        self.assertTrue(evaluated)

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

    def test_export_feed_prunes_successfully_reevaluated_stale_issuer(self):
        stale = {
            "id": "old-spac",
            "company": "Old SPAC",
            "cik": "0002113088",
            "filed": "2026-08-28",
            "form": "S-1",
        }
        unrelated = {
            "id": "other",
            "company": "Operating Co",
            "cik": "0001234567",
            "filed": "2026-08-27",
            "form": "S-1",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s1_watch.json"
            path.write_text(json.dumps({"filings": [stale, unrelated]}), encoding="utf-8")
            payload = s1_monitor.export_feed([], path, processed_ciks={"2113088"})
            self.assertEqual([item["id"] for item in payload["filings"]], ["other"])

    def test_export_feed_replaces_old_accession_for_reevaluated_issuer(self):
        old = {
            "id": "old-accession",
            "company": "Acme Robotics, Inc.",
            "cik": "0001234567",
            "filed": "2026-08-10",
            "form": "S-1",
        }
        new = {
            "id": "new-accession",
            "company": "Acme Robotics, Inc.",
            "cik": "0001234567",
            "filed": "2026-08-17",
            "form": "S-1/A",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s1_watch.json"
            path.write_text(json.dumps({"filings": [old]}), encoding="utf-8")
            payload = s1_monitor.export_feed([new], path, processed_ciks={"1234567"})
            self.assertEqual([item["id"] for item in payload["filings"]], ["new-accession"])

    def test_queue_record_uses_stable_issuer_id_and_v1_size_field(self):
        filing = s1_monitor._queue_record({
            "id": "0001234567-26-000001",
            "company": "Acme Robotics, Inc.",
            "cik": "1234567",
            "accession_no": "0001234567-26-000001",
            "form": "S-1/A",
            "filed": "2026-08-17",
            "priority": "High",
            "ipo_size": 95_000_000,
            "signals": ["Preliminary offering range disclosed at $18.00–$20.00"],
            "sec_url": "https://www.sec.gov/test",
        })
        self.assertEqual(filing["id"], "s1:0001234567")
        self.assertEqual(filing["people"], [])
        self.assertEqual(filing["value"], 95_000_000)
        self.assertNotIn("ipo_size", filing)

    def test_sync_queue_replaces_older_amendment_for_same_issuer(self):
        old = {
            "id": "s1:0001234567",
            "company": "Acme Robotics, Inc.",
            "cik": "0001234567",
            "accession_no": "old-accession",
            "form": "S-1",
            "filed": "2026-08-10",
            "priority": "Medium",
            "status": "New",
            "value": None,
            "value_label": "—",
            "people_count": 0,
            "signals": ["Initial registration statement filed — IPO is pre-pricing"],
            "people": [],
            "sec_url": "https://www.sec.gov/old",
        }
        new = {
            "id": "new-accession",
            "company": "Acme Robotics, Inc.",
            "cik": "0001234567",
            "accession_no": "new-accession",
            "form": "S-1/A",
            "filed": "2026-08-17",
            "priority": "High",
            "signals": ["Preliminary offering range disclosed at $18.00–$20.00"],
            "sec_url": "https://www.sec.gov/new",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "filings.json"
            path.write_text(json.dumps({"filings": [old]}), encoding="utf-8")
            payload = s1_monitor.sync_research_queue([new], path)
            self.assertEqual(len(payload["filings"]), 1)
            self.assertEqual(payload["filings"][0]["accession_no"], "new-accession")
            self.assertEqual(payload["filings"][0]["form"], "S-1/A")
            self.assertFalse(Path(str(path) + ".tmp").exists())
            with path.with_suffix(".csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["form"], "S-1/A")
            self.assertEqual(rows[0]["filing_price"], "")

    def test_sync_queue_prunes_processed_s1_that_no_longer_qualifies(self):
        stale = {
            "id": "s1:0002112634",
            "company": "Sensei Harbor Corp.",
            "cik": "0002112634",
            "form": "S-1/A",
            "filed": "20260818",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "filings.json"
            path.write_text(json.dumps({"filings": [stale]}), encoding="utf-8")
            payload = s1_monitor.sync_research_queue([], path, processed_ciks={"2112634"})
            self.assertEqual(payload["filings"], [])

    def test_sync_queue_removes_prepricing_row_after_424b4(self):
        prepricing = {
            "id": "s1:0001234567",
            "company": "Acme Robotics, Inc.",
            "cik": "0001234567",
            "form": "S-1/A",
            "filed": "2026-08-16",
        }
        priced = {
            "id": "priced-accession",
            "company": "Acme Robotics, Inc.",
            "cik": "0001234567",
            "form": "424B4",
            "filed": "2026-08-17",
        }
        new = {
            "id": "new-s1-accession",
            "company": "Acme Robotics, Inc.",
            "cik": "0001234567",
            "accession_no": "new-s1-accession",
            "form": "S-1/A",
            "filed": "2026-08-17",
            "priority": "High",
            "signals": [],
            "sec_url": "https://www.sec.gov/new",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "filings.json"
            path.write_text(json.dumps({"filings": [prepricing, priced]}), encoding="utf-8")
            payload = s1_monitor.sync_research_queue([new], path)
            self.assertEqual([item["id"] for item in payload["filings"]], ["priced-accession"])


if __name__ == "__main__":
    unittest.main()

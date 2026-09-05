import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("SEC_EDGAR_USER_AGENT", "Research Monitor test@example.com")

import s1_monitor


class S1TickerSourceTests(unittest.TestCase):
    @patch("s1_monitor.filing_parser.parse_filing")
    @patch("s1_monitor.filing_parser.fetch_document")
    @patch("s1_monitor.filing_parser.find_primary_document_url")
    @patch("s1_monitor.edgar_client.get_primary_ticker")
    @patch("s1_monitor.edgar_client.is_first_time_registrant", return_value=True)
    @patch("s1_monitor.edgar_client.is_us_based", return_value=True)
    def test_prefers_ticker_disclosed_in_s1_cover(
        self, us_based, first_time, sec_ticker, primary_doc, fetch_doc, parse_filing
    ):
        primary_doc.return_value = "https://sec.test/orion-s1.htm"
        soup = Mock()
        soup.get_text.return_value = "This is the initial public offering of our common stock."
        fetch_doc.return_value = soup
        parse_filing.return_value = {
            "price_range": {"range_low": None, "range_high": None},
            "cover_page": {
                "ticker": "ORIN",
                "exchange": "Nasdaq",
                "offering_price": None,
                "offering_size_shares": None,
            },
        }

        record = s1_monitor.enrich_record({
            "company_name": "Orion180 Insurance Group Inc.",
            "cik": "2124472",
            "form_type": "S-1",
            "filing_date": "2026-08-20",
            "accession_no": "0001628280-26-058231",
        })

        self.assertIsNotNone(record)
        self.assertEqual(record["ticker"], "ORIN")
        sec_ticker.assert_not_called()

    def test_carries_forward_unambiguous_ticker_to_later_amendment(self):
        history = [{
            "id": "0001628280-26-059639",
            "cik": "0002133037",
            "form": "S-1",
            "filed": "2026-09-01",
            "ticker": "SBE",
        }]
        records = [{
            "id": "0001628280-26-060761",
            "cik": "0002133037",
            "form": "S-1/A",
            "filed": "2026-09-04",
            "ticker": "",
        }]

        s1_monitor._preserve_unambiguous_ticker_lineage(records, history)

        self.assertEqual(records[0]["ticker"], "SBE")

    def test_conflicting_prior_tickers_leave_amendment_blank(self):
        history = [
            {
                "id": "old-1",
                "cik": "0002133037",
                "form": "S-1",
                "filed": "2026-09-01",
                "ticker": "SBE",
            },
            {
                "id": "old-2",
                "cik": "0002133037",
                "form": "S-1/A",
                "filed": "2026-09-02",
                "ticker": "SBEN",
            },
        ]
        records = [{
            "id": "new",
            "cik": "0002133037",
            "form": "S-1/A",
            "filed": "2026-09-04",
            "ticker": "",
        }]

        s1_monitor._preserve_unambiguous_ticker_lineage(records, history)

        self.assertEqual(records[0]["ticker"], "")

    def test_same_day_ticker_is_not_used_to_infer_order(self):
        history = [{
            "id": "same-day",
            "cik": "0002133037",
            "form": "S-1",
            "filed": "2026-09-04",
            "ticker": "SBE",
        }]
        records = [{
            "id": "new",
            "cik": "0002133037",
            "form": "S-1/A",
            "filed": "2026-09-04",
            "ticker": "",
        }]

        s1_monitor._preserve_unambiguous_ticker_lineage(records, history)

        self.assertEqual(records[0]["ticker"], "")

    def test_existing_amendment_ticker_is_never_overwritten(self):
        history = [{
            "id": "old",
            "cik": "0002133037",
            "form": "S-1",
            "filed": "2026-09-01",
            "ticker": "SBE",
        }]
        records = [{
            "id": "new",
            "cik": "0002133037",
            "form": "S-1/A",
            "filed": "2026-09-04",
            "ticker": "SBEX",
        }]

        s1_monitor._preserve_unambiguous_ticker_lineage(records, history)

        self.assertEqual(records[0]["ticker"], "SBEX")


if __name__ == "__main__":
    unittest.main()

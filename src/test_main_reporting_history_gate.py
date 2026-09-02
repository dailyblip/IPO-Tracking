import unittest
from unittest.mock import patch

import main


class MainReportingHistoryGateTests(unittest.TestCase):
    def _submissions(self, forms, dates):
        return {
            "filings": {
                "recent": {
                    "form": forms,
                    "filingDate": dates,
                }
            }
        }

    @patch("main.edgar_client._get_headers", return_value={"User-Agent": "test"})
    @patch("main.edgar_client._request_json")
    def test_first_breach_august_31_followon_is_rejected_by_prior_8k(
        self, request_json, _headers
    ):
        request_json.return_value = self._submissions(
            ["424B4", "8-K", "424B4", "S-1/A"],
            ["2026-08-31", "2026-08-25", "2026-08-20", "2026-08-07"],
        )

        self.assertFalse(
            main._is_first_time_registrant_as_of("1892704", "2026-08-31")
        )

    @patch("main.edgar_client._get_headers", return_value={"User-Agent": "test"})
    @patch("main.edgar_client._request_json")
    def test_prior_10q_rejects_followon_before_document_parse_or_quote_lookup(
        self, request_json, _headers
    ):
        request_json.return_value = self._submissions(
            ["424B4", "10-Q", "S-1/A"],
            ["2026-09-01", "2026-08-15", "2026-07-01"],
        )

        self.assertFalse(
            main._is_first_time_registrant_as_of("1234567", "2026-09-01")
        )

    @patch("main.edgar_client._get_headers", return_value={"User-Agent": "test"})
    @patch("main.edgar_client._request_json")
    def test_transition_report_rejects_followon_before_document_parse_or_quote_lookup(
        self, request_json, _headers
    ):
        for reporting_form in ("10-QT", "10-QT/A", "10-KT", "10-KT/A"):
            with self.subTest(reporting_form=reporting_form):
                request_json.return_value = self._submissions(
                    ["424B4", reporting_form, "S-1/A"],
                    ["2026-09-01", "2026-08-15", "2026-07-01"],
                )
                self.assertFalse(
                    main._is_first_time_registrant_as_of("1234567", "2026-09-01")
                )

    @patch("main.edgar_client._get_headers", return_value={"User-Agent": "test"})
    @patch("main.edgar_client._request_json")
    def test_same_day_reporting_form_does_not_guess_filing_order(
        self, request_json, _headers
    ):
        request_json.return_value = self._submissions(
            ["8-K", "424B4", "S-1/A"],
            ["2026-09-01", "2026-09-01", "2026-08-20"],
        )

        self.assertTrue(
            main._is_first_time_registrant_as_of("1234567", "2026-09-01")
        )

    @patch("main.edgar_client._get_headers", return_value={"User-Agent": "test"})
    @patch("main.edgar_client._request_json")
    def test_later_reporting_form_does_not_reclassify_historical_ipo(
        self, request_json, _headers
    ):
        request_json.return_value = self._submissions(
            ["10-Q", "8-K", "424B4", "S-1/A"],
            ["2026-11-01", "2026-08-25", "2026-08-20", "2026-08-07"],
        )

        self.assertTrue(
            main._is_first_time_registrant_as_of("1892704", "2026-08-20")
        )


if __name__ == "__main__":
    unittest.main()

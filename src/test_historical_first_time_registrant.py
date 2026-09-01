import unittest
from unittest.mock import patch

import main


class HistoricalFirstTimeRegistrantTests(unittest.TestCase):
    @patch("main.edgar_client._get_headers", return_value={"User-Agent": "test"})
    @patch("main.edgar_client._request_json")
    def test_later_10k_does_not_reclassify_historical_ipo(self, request_json, _headers):
        request_json.return_value = {
            "filings": {
                "recent": {
                    "form": ["10-K", "424B4", "S-1/A"],
                    "filingDate": ["2026-08-15", "2026-03-20", "2026-03-10"],
                }
            }
        }

        self.assertTrue(
            main._is_first_time_registrant_as_of("1234567", "2026-03-20")
        )

    @patch("main.edgar_client._get_headers", return_value={"User-Agent": "test"})
    @patch("main.edgar_client._request_json")
    def test_prior_10k_still_excludes_followon(self, request_json, _headers):
        request_json.return_value = {
            "filings": {
                "recent": {
                    "form": ["10-K", "424B4", "10-K"],
                    "filingDate": ["2026-08-15", "2026-03-20", "2025-03-01"],
                }
            }
        }

        self.assertFalse(
            main._is_first_time_registrant_as_of("1234567", "2026-03-20")
        )

    @patch("main._is_first_time_registrant_as_of", return_value=False)
    @patch("main.edgar_client.is_us_based", return_value=True)
    def test_process_filing_passes_candidate_424b4_date(self, _us_based, first_time):
        result = main.process_filing({
            "company_name": "Historical IPO Co",
            "cik": "1234567",
            "accession_no": "0001234567-26-000001",
            "filing_date": "2026-03-20",
            "form_type": "424B4",
        })

        self.assertEqual(result, [])
        first_time.assert_called_once_with("1234567", "2026-03-20")

    @patch("main.edgar_client.is_first_time_registrant", return_value=True)
    def test_missing_candidate_date_preserves_current_state_fallback(self, first_time):
        self.assertTrue(main._is_first_time_registrant_as_of("1234567"))
        first_time.assert_called_once_with("1234567")

    def test_invalid_candidate_date_fails_closed(self):
        with self.assertRaises(ValueError):
            main._is_first_time_registrant_as_of("1234567", "03/20/2026")


if __name__ == "__main__":
    unittest.main()

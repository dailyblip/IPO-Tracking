import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("SEC_EDGAR_USER_AGENT", "Research Monitor test@example.com")

import edgar_client


class EdgarDiscoveryTests(unittest.TestCase):
    def test_cleans_cik_suffix_from_efts_company_name(self):
        self.assertEqual(
            edgar_client._clean_company_name("Acme Robotics  (CIK 0001234567)"),
            "Acme Robotics",
        )

    @patch("edgar_client.requests.get")
    def test_daily_index_fallback_parses_424b4_only(self, get):
        response = Mock()
        response.status_code = 200
        response.text = """Description
-----
1234567|Acme Robotics, Inc.|424B4|2026-08-17|edgar/data/1234567/0001234567-26-000001.txt
7654321|Unrelated Company|10-K|2026-08-17|edgar/data/7654321/0007654321-26-000002.txt
"""
        response.raise_for_status.return_value = None
        get.return_value = response

        results = edgar_client._find_from_daily_indexes(
            "2026-08-17", "2026-08-17", 10, {"User-Agent": "test"}
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["company_name"], "Acme Robotics, Inc.")
        self.assertEqual(results[0]["accession_no"], "0001234567-26-000001")
        self.assertEqual(results[0]["form_type"], "424B4")

    @patch("edgar_client._find_from_daily_indexes")
    @patch("edgar_client._request_json")
    def test_efts_failure_uses_daily_index(self, request_json, daily_indexes):
        request_json.side_effect = edgar_client.EdgarClientError("500")
        daily_indexes.return_value = [{
            "company_name": "Fallback Co",
            "cik": "123",
            "accession_no": "fallback-accession",
            "filing_date": "2026-08-17",
            "form_type": "424B4",
        }]

        results = edgar_client.find_recent_424b4_filings(
            start_date="2026-08-17", end_date="2026-08-17"
        )

        self.assertEqual(results[0]["company_name"], "Fallback Co")
        daily_indexes.assert_called_once()


if __name__ == "__main__":
    unittest.main()

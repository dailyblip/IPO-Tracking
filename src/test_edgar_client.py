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


    def test_cleans_ticker_suffix_and_keeps_ticker_hint(self):
        label = "Apnimed, Inc.  (APMD)"
        self.assertEqual(edgar_client._clean_company_name(label), "Apnimed, Inc.")
        self.assertEqual(edgar_client._extract_ticker_from_company_name(label), "APMD")

    def test_spac_detection_is_issuer_anchored(self):
        operating_text = (
            "We are a clinical-stage biotechnology company. "
            "Our risk factors discuss special purpose acquisition companies."
        )
        self.assertFalse(
            edgar_client.check_spac_indicators(
                operating_text, company_name="BlossomHill Therapeutics, Inc."
            )
        )
        self.assertTrue(
            edgar_client.check_spac_indicators(
                operating_text, company_name="Pinnacle Acquisition Corp"
            )
        )
        self.assertTrue(
            edgar_client.check_spac_indicators(
                "We are a newly formed blank check company.",
                company_name="Thunder Bridge V, Ltd.",
            )
        )

    @patch("edgar_client.requests.get")
    def test_primary_ticker_uses_sec_submission_profile(self, get):
        response = Mock()
        response.json.return_value = {"tickers": ["ACME", "ACMEW"]}
        response.raise_for_status.return_value = None
        get.return_value = response
        self.assertEqual(edgar_client.get_primary_ticker("1234567"), "ACME")


    def test_direct_listing_is_not_a_qualifying_primary_ipo(self):
        self.assertTrue(
            edgar_client.check_direct_listing_indicators(
                "Registered stockholders may sell shares pursuant to a direct listing."
            )
        )
        self.assertTrue(
            edgar_client.check_direct_listing_indicators(
                "This listing is not an underwritten initial public offering."
            )
        )
        self.assertFalse(
            edgar_client.check_direct_listing_indicators(
                "This is the initial public offering of our common stock."
            )
        )


    def test_business_location_formats_domestic_and_foreign(self):
        with patch.object(edgar_client, "_request_json", return_value={"addresses":{"business":{"city":"Palo Alto","stateOrCountry":"CA","country":"US"}}}):
            self.assertEqual(edgar_client.get_business_location("1"), "Palo Alto, CA")
        with patch.object(edgar_client, "_request_json", return_value={"addresses":{"business":{"city":"Milan","stateOrCountry":"","country":"IT"}}}):
            self.assertEqual(edgar_client.get_business_location("1"), "IT")

if __name__ == "__main__":
    unittest.main()

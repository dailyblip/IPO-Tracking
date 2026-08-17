import unittest
from datetime import date
from unittest.mock import Mock, patch

import main


class LookbackTests(unittest.TestCase):
    def test_monday_includes_thursday_and_friday(self):
        self.assertEqual(main._default_lookback_days(date(2026, 8, 17)), 4)

    def test_midweek_uses_two_calendar_days(self):
        self.assertEqual(main._default_lookback_days(date(2026, 8, 19)), 2)

    def test_sunday_reaches_back_to_thursday(self):
        self.assertEqual(main._default_lookback_days(date(2026, 8, 23)), 3)

    @patch("main.filing_parser.parse_filing")
    @patch("main.edgar_client.find_matching_s1", return_value={})
    @patch("main.edgar_client.is_first_time_registrant", return_value=True)
    @patch("main.edgar_client.is_us_based", return_value=True)
    def test_skips_filer_without_domestic_s1(self, _us, _first, _s1, parse_filing):
        rows = main.process_filing({
            "company_name": "Foreign Issuer",
            "cik": "2006960",
            "accession_no": "0001193125-26-351136",
        })
        self.assertEqual(rows, [])
        parse_filing.assert_not_called()


    def test_qualifying_filing_survives_missing_owner_parse(self):
        parsed_424b4 = {
            "cover_page": {
                "ticker": None,
                "offering_price": 18.0,
                "offering_size_shares": 5_000_000,
            },
            "principal_stockholders": [],
            "management_bios": {},
            "lockup_info": {"raw_text": None},
            "diagnostics": {},
        }
        parsed_s1 = {"price_range": {"range_low": 16.0, "range_high": 18.0}}
        filing_document = Mock()
        filing_document.get_text.return_value = "We are an operating biotechnology company."

        with (
            patch("main.edgar_client.is_us_based", return_value=True),
            patch("main.edgar_client.is_first_time_registrant", return_value=True),
            patch(
                "main.edgar_client.find_matching_s1",
                return_value={
                    "accession_no": "0001234567-26-000001",
                    "filing_date": "2026-07-01",
                },
            ),
            patch("main.edgar_client.check_spac_indicators", return_value=False),
            patch("main.edgar_client.get_primary_ticker", return_value="ACME"),
            patch("main.filing_parser.find_primary_document_url", return_value="https://sec.test/doc"),
            patch("main.filing_parser.parse_filing", side_effect=[parsed_424b4, parsed_s1]),
            patch("main.filing_parser.fetch_document", return_value=filing_document),
            patch("main.price_lookup.get_current_price", return_value=20.0),
            patch("main.stanford_grader.grade_stanford_affiliation") as grader,
        ):
            rows = main.process_filing({
                "company_name": "Acme Therapeutics, Inc.",
                "cik": "1234567",
                "accession_no": "0001234567-26-000002",
                "filing_date": "2026-08-01",
            })

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Ticker"], "ACME")
        self.assertEqual(rows[0]["Holder Name"], "")
        self.assertEqual(rows[0]["Amount Raised"], 90_000_000)
        grader.assert_not_called()


if __name__ == "__main__":
    unittest.main()

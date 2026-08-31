import unittest
from unittest.mock import Mock, patch

import main


class NullableTickerQcTests(unittest.TestCase):
    def test_unresolved_ticker_reaches_qc_as_empty_string(self):
        parsed_424b4 = {
            "cover_page": {
                "ticker": None,
                "offering_price": 15.0,
                "offering_size_shares": 10_000_000,
            },
            "principal_stockholders": [
                {"name": "Example Holder", "shares": 1_000_000},
            ],
            "management_bios": {},
            "lockup_info": {"raw_text": None},
            "diagnostics": {},
        }
        parsed_s1 = {"price_range": {"range_low": 13.0, "range_high": 15.0}}
        filing_document = Mock()
        filing_document.get_text.return_value = "We are an operating technology company."

        with (
            patch("main.edgar_client.is_us_based", return_value=True),
            patch("main.edgar_client.is_first_time_registrant", return_value=True),
            patch(
                "main.edgar_client.find_matching_s1",
                return_value={
                    "accession_no": "0001234567-26-000001",
                    "filing_date": "2026-05-01",
                },
            ),
            patch("main.edgar_client.check_spac_indicators", return_value=False),
            patch("main.edgar_client.check_direct_listing_indicators", return_value=False),
            patch("main.edgar_client.get_primary_ticker", return_value=None),
            patch("main.filing_parser.find_primary_document_url", return_value="https://sec.test/doc"),
            patch("main.filing_parser.parse_filing", side_effect=[parsed_424b4, parsed_s1]),
            patch("main.filing_parser.fetch_document", return_value=filing_document),
            patch("main.stanford_grader.grade_stanford_affiliation", return_value={"grade": 0, "justification": "No Stanford evidence."}),
        ):
            rows = main.process_filing({
                "company_name": "Tickerless Operating Co.",
                "cik": "1234567",
                "accession_no": "0001234567-26-000002",
                "filing_date": "2026-05-12",
            })

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Ticker"], "")
        self.assertEqual(rows[0]["Holder Name"], "Example Holder")


if __name__ == "__main__":
    unittest.main()

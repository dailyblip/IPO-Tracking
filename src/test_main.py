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

    def test_person_bio_matches_name_variants_without_using_full_text(self):
        bios = {
            "Jane Founder, Ph.D.": "Jane earned a degree from Stanford University.",
            "_full_text": "Another director attended Stanford University.",
        }
        self.assertIn("Jane earned", main._person_bio(bios, "Jane Founder"))
        self.assertEqual(main._person_bio(bios, "John Investor"), "")

    def test_stanford_highlight_requires_exact_university_reference(self):
        self.assertTrue(main._mentions_stanford_university(
            "She received her MBA from Stanford University."
        ))
        self.assertFalse(main._mentions_stanford_university(
            "He previously worked at Stanford Health Care."
        ))

    @patch("main.dashboard_export.refresh_market_prices")
    @patch("main.price_lookup.get_current_prices", return_value={"ACME": 31.25})
    def test_refreshes_each_dashboard_ticker_once(self, get_prices, refresh):
        dashboard = {"filings": [
            {"ticker": "ACME"},
            {"ticker": "acme"},
            {"ticker": ""},
        ]}
        refresh.return_value = dashboard

        self.assertIs(main._refresh_dashboard_prices(dashboard), dashboard)

        get_prices.assert_called_once_with(["ACME"])
        refresh.assert_called_once()

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


# QA arithmetic behavior is covered deterministically without live SEC calls.
class ProspectQaArithmeticTests(unittest.TestCase):
    def test_qc_flags_cross_field_inconsistencies(self):
        import qc_review
        row={"Company Name":"X","Ticker":"X","Date of Pricing":"2026-01-01","Actual Price":10,"Current Price":12,"Holder Name":"Jane Doe","Shares Before IPO":1000,"Shares Sold in IPO":100,"Shares After IPO":800,"Shares":800,"Cash Realized IPO":900,"Cash Value":9000,"IPO Size (Shares)":10000,"Amount Raised":None}
        issues=qc_review.check_prospect_integrity(row)
        self.assertTrue(any("reconcile" in x for x in issues))
        self.assertTrue(any("cash proceeds" in x for x in issues))
        self.assertTrue(any("Offering value" in x for x in issues))


class StanfordConfirmationThresholdTests(unittest.TestCase):
    def test_stanford_confirmation_requires_grade_five(self):
        from pathlib import Path
        source=Path(__file__).with_name("main.py").read_text(encoding="utf-8")
        self.assertIn('stanford_result.get("grade") in (5, "5")', source)
        self.assertNotIn('stanford_result.get("grade") in (1, "1"', source)

import unittest
from unittest import mock

import filing_price_history


class FilingPriceHistoryTests(unittest.TestCase):
    def priced_row(self, **overrides):
        row = {
            "id": "final-1",
            "company": "Example Corp.",
            "ticker": "EXM",
            "cik": "1234567",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-08-20",
            "pricing_date": "2026-08-20",
            "offering_price": 17.0,
            "filing_price": None,
        }
        row.update(overrides)
        return row

    def test_blank_priced_row_scans_preceding_history_until_range_found(self):
        calls = []
        history = [
            {"form_type": "S-1/A", "accession_no": "amend-2", "filing_date": "2026-08-18"},
            {"form_type": "S-1/A", "accession_no": "amend-1", "filing_date": "2026-08-15"},
            {"form_type": "S-1", "accession_no": "initial", "filing_date": "2026-08-01"},
        ]

        def history_loader(cik, pricing_date):
            self.assertEqual(cik, "0001234567")
            self.assertEqual(pricing_date, "2026-08-20")
            return history

        def registration_loader(cik, metadata):
            calls.append(metadata["accession_no"])
            if metadata["accession_no"] == "amend-2":
                return {"price_range": {"range_low": None, "range_high": None}}, "https://www.sec.gov/amend-2"
            if metadata["accession_no"] == "amend-1":
                return {"price_range": {"range_low": 14, "range_high": 16}}, "https://www.sec.gov/amend-1"
            raise AssertionError("scan should stop after authoritative range is found")

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [self.priced_row()]},
            history_loader=history_loader,
            registration_loader=registration_loader,
        )

        filing = payload["filings"][0]
        self.assertEqual(calls, ["amend-2", "amend-1"])
        self.assertEqual(filing["filing_price"], "14-16")
        self.assertEqual(filing["filing_price_source"]["source"], "SEC EDGAR")
        self.assertEqual(filing["filing_price_source"]["form"], "S-1/A")
        self.assertEqual(filing["filing_price_source"]["filing_date"], "2026-08-15")
        self.assertEqual(filing["filing_price_source"]["accession_no"], "amend-1")
        self.assertEqual(filing["filing_price_source"]["sec_url"], "https://www.sec.gov/amend-1")
        self.assertEqual((recovered, checked), (1, 1))

    def test_blank_priced_row_recovers_fixed_expected_price_with_provenance(self):
        history = [
            {
                "form_type": "S-1/A",
                "accession_no": "0001628280-26-040364",
                "filing_date": "2026-06-03",
            },
        ]

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {
                "filings": [
                    self.priced_row(
                        company="Space Exploration Technologies Corp",
                        ticker="SPCX",
                        cik="0001181412",
                        pricing_date="2026-06-12",
                        offering_price=135.0,
                    )
                ]
            },
            history_loader=lambda cik, pricing_date: history,
            registration_loader=lambda cik, metadata: (
                {"price_range": {"range_low": 135.0, "range_high": 135.0}},
                "https://www.sec.gov/Archives/edgar/data/1181412/"
                "000162828026040364/0001628280-26-040364-index.htm",
            ),
        )

        filing = payload["filings"][0]
        self.assertEqual(filing["filing_price"], "135")
        self.assertEqual(
            filing["filing_price_source"]["accession_no"],
            "0001628280-26-040364",
        )
        self.assertEqual((recovered, checked), (1, 1))

    def test_verified_history_without_disclosed_range_keeps_blank(self):
        history = [
            {"form_type": "S-1/A", "accession_no": "amend", "filing_date": "2026-08-18"},
            {"form_type": "S-1", "accession_no": "initial", "filing_date": "2026-08-01"},
        ]

        def registration_loader(cik, metadata):
            return {"price_range": {"range_low": None, "range_high": None}}, f"https://www.sec.gov/{metadata['accession_no']}"

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [self.priced_row()]},
            history_loader=lambda cik, pricing_date: history,
            registration_loader=registration_loader,
        )

        filing = payload["filings"][0]
        self.assertIsNone(filing["filing_price"])
        self.assertNotIn("filing_price_source", filing)
        self.assertEqual((recovered, checked), (0, 1))

    def test_all_registration_parse_failures_fail_closed(self):
        history = [
            {"form_type": "S-1/A", "accession_no": "amend", "filing_date": "2026-08-18"},
            {"form_type": "S-1", "accession_no": "initial", "filing_date": "2026-08-01"},
        ]

        with self.assertRaises(filing_price_history.FilingPriceHistoryError):
            filing_price_history.recover_payload_filing_prices(
                {"filings": [self.priced_row()]},
                history_loader=lambda cik, pricing_date: history,
                registration_loader=lambda cik, metadata: (_ for _ in ()).throw(RuntimeError("SEC parse failed")),
            )

    def test_existing_preliminary_price_with_sec_source_validates_history_lineage(self):
        history_calls = []
        history = [
            {
                "form_type": "S-1/A",
                "accession_no": "0001193125-26-123456",
                "filing_date": "2026-08-18",
                "file_number": "333-300001",
            },
        ]

        def history_loader(cik, pricing_date):
            history_calls.append((cik, pricing_date))
            return history

        def registration_should_not_run(*args, **kwargs):
            raise AssertionError("matching sourced filing price should not be reparsed")

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [self.priced_row(
                filing_price="15-17",
                filing_price_source={
                    "source": "SEC EDGAR",
                    "form": "S-1/A",
                    "filing_date": "2026-08-18",
                    "accession_no": "0001193125-26-123456",
                    "sec_url": "https://www.sec.gov/amend",
                },
            )]},
            history_loader=history_loader,
            registration_loader=registration_should_not_run,
        )
        self.assertEqual(history_calls, [("0001234567", "2026-08-20")])
        self.assertEqual(payload["filings"][0]["filing_price"], "15-17")
        self.assertEqual((recovered, checked), (0, 0))

    def test_existing_source_outside_ipo_chronology_is_rechecked(self):
        history = [
            {"form_type": "S-1/A", "accession_no": "valid-amend", "filing_date": "2026-08-18"},
            {"form_type": "S-1", "accession_no": "initial", "filing_date": "2026-08-01"},
        ]

        for invalid_source_date in ("2026-08-21", "2026-07-31"):
            with self.subTest(invalid_source_date=invalid_source_date):
                payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
                    {"filings": [self.priced_row(
                        filing_date="2026-08-01",
                        filing_price="99-101",
                        filing_price_source={
                            "source": "SEC EDGAR",
                            "form": "S-1/A",
                            "filing_date": invalid_source_date,
                            "accession_no": "stale-source",
                            "sec_url": "https://www.sec.gov/stale-source",
                        },
                    )]},
                    history_loader=lambda cik, pricing_date: history,
                    registration_loader=lambda cik, metadata: (
                        {"price_range": {"range_low": 15, "range_high": 17}},
                        "https://www.sec.gov/valid-amend",
                    ),
                )

                filing = payload["filings"][0]
                self.assertEqual(filing["filing_price"], "15-17")
                self.assertEqual(
                    filing["filing_price_source"]["accession_no"], "valid-amend"
                )
                self.assertEqual(
                    filing["filing_price_source"]["filing_date"], "2026-08-18"
                )
                self.assertEqual((recovered, checked), (1, 1))

    def test_existing_preliminary_price_without_source_recovers_provenance(self):
        history = [
            {"form_type": "S-1/A", "accession_no": "amend", "filing_date": "2026-08-18"},
            {"form_type": "S-1", "accession_no": "initial", "filing_date": "2026-08-01"},
        ]

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [self.priced_row(filing_price="15-17")]},
            history_loader=lambda cik, pricing_date: history,
            registration_loader=lambda cik, metadata: (
                {"price_range": {"range_low": 15, "range_high": 17}},
                f"https://www.sec.gov/{metadata['accession_no']}",
            ),
        )

        filing = payload["filings"][0]
        self.assertEqual(filing["filing_price"], "15-17")
        self.assertEqual(filing["filing_price_source"]["source"], "SEC EDGAR")
        self.assertEqual(filing["filing_price_source"]["accession_no"], "amend")
        self.assertEqual((recovered, checked), (1, 1))

    def test_unprovenanced_existing_price_without_disclosed_range_fails_closed(self):
        history = [
            {"form_type": "S-1/A", "accession_no": "amend", "filing_date": "2026-08-18"},
        ]

        with self.assertRaises(filing_price_history.FilingPriceHistoryError):
            filing_price_history.recover_payload_filing_prices(
                {"filings": [self.priced_row(filing_price="15-17")]},
                history_loader=lambda cik, pricing_date: history,
                registration_loader=lambda cik, metadata: (
                    {"price_range": {"range_low": None, "range_high": None}},
                    "https://www.sec.gov/amend",
                ),
            )

    def test_prepricing_row_is_not_subject_to_final_history_gate(self):
        row = self.priced_row(
            form="S-1/A",
            stage="Pre-pricing",
            pricing_date=None,
            offering_price=None,
            price_range="14-16",
        )

        def should_not_run(*args, **kwargs):
            raise AssertionError("history lookup should not run for pre-pricing row")

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [row]},
            history_loader=should_not_run,
            registration_loader=should_not_run,
        )
        self.assertEqual(payload["filings"][0], row)
        self.assertEqual((recovered, checked), (0, 0))

    def test_lyntris_between_wording_is_recovered(self):
        text = (
            "It is currently estimated that the initial public offering price per share "
            "will be between $19.00 and $22.00."
        )
        self.assertEqual(
            filing_price_history._extract_explicit_price_range_from_text(text),
            {"range_low": 19.0, "range_high": 22.0},
        )

    def test_spacex_fixed_expected_price_wording_is_recovered(self):
        text = (
            "We are offering 555,555,555 shares of our Class A common stock. "
            "Currently, no public market exists for our Class A common stock. "
            "We expect the initial public offering price to be $135.00 per share."
        )
        self.assertEqual(
            filing_price_history._extract_explicit_price_range_from_text(text),
            {"range_low": 135.0, "range_high": 135.0},
        )
        self.assertEqual(filing_price_history._format_range(135.0, 135.0), "135")

    def test_fee_table_maximum_price_is_not_treated_as_preliminary_range(self):
        text = (
            "Proposed Maximum Offering Price Per Unit $22.00 Maximum Aggregate "
            "Offering Price $507,200,012.00."
        )
        self.assertEqual(
            filing_price_history._extract_explicit_price_range_from_text(text),
            {"range_low": None, "range_high": None},
        )

    def test_parse_s1_history_entry_uses_fallback_when_legacy_parser_misses(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(
            "It is currently estimated that the initial public offering price per share "
            "will be between $19.00 and $22.00.",
            "html.parser",
        )
        metadata = {"accession_no": "0001193125-26-346328"}
        with (
            mock.patch.object(
                filing_price_history.edgar_client,
                "build_filing_index_url",
                return_value="https://www.sec.gov/index",
            ),
            mock.patch.object(
                filing_price_history.filing_parser,
                "find_primary_document_url",
                return_value="https://www.sec.gov/document",
            ),
            mock.patch.object(
                filing_price_history.filing_parser,
                "fetch_document",
                return_value=soup,
            ),
            mock.patch.object(
                filing_price_history.filing_parser,
                "extract_price_range",
                return_value={"range_low": None, "range_high": None},
            ),
        ):
            parsed, source_url = filing_price_history.parse_s1_history_entry(
                "0002132582", metadata
            )

        self.assertEqual(parsed["price_range"], {"range_low": 19.0, "range_high": 22.0})
        self.assertEqual(source_url, "https://www.sec.gov/index")

    def test_parse_s1_history_entry_recovers_fixed_expected_price(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(
            "We expect the initial public offering price to be $135.00 per share.",
            "html.parser",
        )
        metadata = {"accession_no": "0001628280-26-040364"}
        with (
            mock.patch.object(
                filing_price_history.edgar_client,
                "build_filing_index_url",
                return_value="https://www.sec.gov/spacex-index",
            ),
            mock.patch.object(
                filing_price_history.filing_parser,
                "find_primary_document_url",
                return_value="https://www.sec.gov/spacex-document",
            ),
            mock.patch.object(
                filing_price_history.filing_parser,
                "fetch_document",
                return_value=soup,
            ),
            mock.patch.object(
                filing_price_history.filing_parser,
                "extract_price_range",
                return_value={"range_low": None, "range_high": None},
            ),
        ):
            parsed, source_url = filing_price_history.parse_s1_history_entry(
                "0001181412", metadata
            )

        self.assertEqual(parsed["price_range"], {"range_low": 135.0, "range_high": 135.0})
        self.assertEqual(source_url, "https://www.sec.gov/spacex-index")


if __name__ == "__main__":
    unittest.main()

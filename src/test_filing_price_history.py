import unittest

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

    def test_existing_preliminary_price_skips_history_lookup(self):
        def should_not_run(*args, **kwargs):
            raise AssertionError("history lookup should not run for populated filing price")

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [self.priced_row(filing_price="15-17")]},
            history_loader=should_not_run,
            registration_loader=should_not_run,
        )
        self.assertEqual(payload["filings"][0]["filing_price"], "15-17")
        self.assertEqual((recovered, checked), (0, 0))

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


if __name__ == "__main__":
    unittest.main()

import unittest

import filing_price_history


class FilingPriceNewerAmendmentTests(unittest.TestCase):
    def priced_row(self, **overrides):
        row = {
            "id": "final-newer-amendment",
            "company": "Example Corp.",
            "ticker": "EXM",
            "cik": "1234567",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-08-20",
            "filing_date": "2026-08-01",
            "pricing_date": "2026-08-20",
            "offering_price": 17.0,
            "filing_price": "15-17",
            "price_range": "15-17",
            "filing_price_source": {
                "source": "SEC EDGAR",
                "form": "S-1/A",
                "filing_date": "2026-08-15",
                "accession_no": "0001193125-26-111111",
                "sec_url": "https://www.sec.gov/old-amendment",
            },
        }
        row.update(overrides)
        return row

    def history(self):
        return [
            {
                "form_type": "S-1/A",
                "accession_no": "0001193125-26-222222",
                "filing_date": "2026-08-18",
                "file_number": "333-300001",
            },
            {
                "form_type": "S-1/A",
                "accession_no": "0001193125-26-111111",
                "filing_date": "2026-08-15",
                "file_number": "333-300001",
            },
            {
                "form_type": "S-1",
                "accession_no": "0001193125-26-000001",
                "filing_date": "2026-08-01",
                "file_number": "333-300001",
            },
        ]

    def test_newer_amendment_replaces_older_sourced_range(self):
        calls = []

        def registration_loader(cik, metadata):
            calls.append(metadata["accession_no"])
            self.assertEqual(cik, "0001234567")
            if metadata["accession_no"] == "0001193125-26-222222":
                return (
                    {"price_range": {"range_low": 16, "range_high": 18}},
                    "https://www.sec.gov/new-amendment",
                )
            raise AssertionError("scan should stop after the newest explicit range")

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [self.priced_row()]},
            history_loader=lambda cik, pricing_date: self.history(),
            registration_loader=registration_loader,
        )

        filing = payload["filings"][0]
        self.assertEqual(calls, ["0001193125-26-222222"])
        self.assertEqual(filing["filing_price"], "16-18")
        self.assertEqual(filing["price_range"], "16-18")
        self.assertEqual(
            filing["filing_price_source"]["accession_no"],
            "0001193125-26-222222",
        )
        self.assertEqual((recovered, checked), (1, 1))

    def test_newer_amendment_without_range_is_inspected_before_older_source(self):
        calls = []

        def registration_loader(cik, metadata):
            calls.append(metadata["accession_no"])
            if metadata["accession_no"] == "0001193125-26-222222":
                return (
                    {"price_range": {"range_low": None, "range_high": None}},
                    "https://www.sec.gov/new-amendment",
                )
            if metadata["accession_no"] == "0001193125-26-111111":
                return (
                    {"price_range": {"range_low": 15, "range_high": 17}},
                    "https://www.sec.gov/old-amendment",
                )
            raise AssertionError("scan should stop after the latest explicit range")

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [self.priced_row()]},
            history_loader=lambda cik, pricing_date: self.history(),
            registration_loader=registration_loader,
        )

        filing = payload["filings"][0]
        self.assertEqual(
            calls,
            ["0001193125-26-222222", "0001193125-26-111111"],
        )
        self.assertEqual(filing["filing_price"], "15-17")
        self.assertEqual(
            filing["filing_price_source"]["accession_no"],
            "0001193125-26-111111",
        )
        self.assertEqual((recovered, checked), (1, 1))

    def test_unreadable_newer_amendment_fails_closed_despite_older_source(self):
        def registration_loader(cik, metadata):
            if metadata["accession_no"] == "0001193125-26-222222":
                raise RuntimeError("SEC parse failed")
            raise AssertionError("older sourced range must not bypass newer failure")

        with self.assertRaises(filing_price_history.FilingPriceHistoryError):
            filing_price_history.recover_payload_filing_prices(
                {"filings": [self.priced_row()]},
                history_loader=lambda cik, pricing_date: self.history(),
                registration_loader=registration_loader,
            )


if __name__ == "__main__":
    unittest.main()

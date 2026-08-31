import unittest

import filing_price_history


class FilingPriceRegistrationLineageTests(unittest.TestCase):
    def _row(self, **overrides):
        row = {
            "id": "priced-reformation-style",
            "company": "Reformation-style issuer",
            "ticker": "TEST",
            "cik": "1787117",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-07-30",
            "filing_date": "2026-07-24",
            "pricing_date": "2026-07-30",
            "offering_price": 15.0,
            "filing_price": None,
        }
        row.update(overrides)
        return row

    def test_same_registration_range_can_predate_row_filing_date(self):
        history = [
            {
                "form_type": "S-1/A",
                "accession_no": "0001104659-26-088001",
                "filing_date": "2026-07-27",
                "file_number": "333-300001",
            },
            {
                "form_type": "S-1/A",
                "accession_no": "0001104659-26-084856",
                "filing_date": "2026-07-20",
                "file_number": "333-300001",
            },
            {
                "form_type": "S-1/A",
                "accession_no": "0001104659-25-099999",
                "filing_date": "2025-11-15",
                "file_number": "333-200001",
            },
        ]
        calls = []

        def registration_loader(cik, metadata):
            calls.append(metadata["accession_no"])
            if metadata["accession_no"] == "0001104659-26-084856":
                return (
                    {"price_range": {"range_low": 15, "range_high": 17}},
                    "https://www.sec.gov/range-amendment",
                )
            if metadata["accession_no"] == "0001104659-25-099999":
                return (
                    {"price_range": {"range_low": 9, "range_high": 11}},
                    "https://www.sec.gov/old-registration",
                )
            return (
                {"price_range": {"range_low": None, "range_high": None}},
                "https://www.sec.gov/current-amendment",
            )

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [self._row()]},
            history_loader=lambda cik, pricing_date: history,
            registration_loader=registration_loader,
        )

        row = payload["filings"][0]
        self.assertEqual(row["filing_price"], "15-17")
        self.assertEqual(
            row["filing_price_source"]["accession_no"],
            "0001104659-26-084856",
        )
        self.assertEqual(
            calls,
            ["0001104659-26-088001", "0001104659-26-084856"],
        )
        self.assertEqual((recovered, checked), (1, 1))

    def test_different_registration_is_never_borrowed(self):
        history = [
            {
                "form_type": "S-1",
                "accession_no": "0001104659-26-080001",
                "filing_date": "2026-07-10",
                "file_number": "333-300001",
            },
            {
                "form_type": "S-1/A",
                "accession_no": "0001104659-26-070001",
                "filing_date": "2026-06-30",
                "file_number": "333-200001",
            },
        ]
        calls = []

        def registration_loader(cik, metadata):
            calls.append(metadata["accession_no"])
            if metadata["accession_no"] == "0001104659-26-070001":
                return (
                    {"price_range": {"range_low": 9, "range_high": 11}},
                    "https://www.sec.gov/old-registration",
                )
            return (
                {"price_range": {"range_low": None, "range_high": None}},
                "https://www.sec.gov/current-initial",
            )

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [self._row(filing_date="2026-07-10")]},
            history_loader=lambda cik, pricing_date: history,
            registration_loader=registration_loader,
        )

        self.assertEqual(calls, ["0001104659-26-080001"])
        self.assertIsNone(payload["filings"][0]["filing_price"])
        self.assertEqual((recovered, checked), (0, 1))

    def test_existing_sec_source_is_rechecked_after_newer_same_registration_filing(self):
        history = [
            {
                "form_type": "S-1/A",
                "accession_no": "0001104659-26-088001",
                "filing_date": "2026-07-27",
                "file_number": "333-300001",
            },
            {
                "form_type": "S-1/A",
                "accession_no": "0001104659-26-084856",
                "filing_date": "2026-07-20",
                "file_number": "333-300001",
            },
            {
                "form_type": "S-1/A",
                "accession_no": "0001104659-26-060001",
                "filing_date": "2026-06-01",
                "file_number": "333-200001",
            },
        ]
        existing_source = {
            "source": "SEC EDGAR",
            "form": "S-1/A",
            "filing_date": "2026-07-20",
            "accession_no": "0001104659-26-084856",
            "sec_url": "https://www.sec.gov/Archives/edgar/data/1787117/000110465926084856/0001104659-26-084856-index.htm",
        }
        calls = []

        def registration_loader(cik, metadata):
            calls.append(metadata["accession_no"])
            if metadata["accession_no"] == "0001104659-26-088001":
                return (
                    {"price_range": {"range_low": None, "range_high": None}},
                    "https://www.sec.gov/current-amendment",
                )
            if metadata["accession_no"] == "0001104659-26-084856":
                return (
                    {"price_range": {"range_low": 15, "range_high": 17}},
                    existing_source["sec_url"],
                )
            raise AssertionError("different registration must not be inspected")

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {
                "filings": [
                    self._row(
                        filing_price="15-17",
                        filing_price_source=existing_source,
                    )
                ]
            },
            history_loader=lambda cik, pricing_date: history,
            registration_loader=registration_loader,
        )

        self.assertEqual(
            calls,
            ["0001104659-26-088001", "0001104659-26-084856"],
        )
        self.assertEqual(payload["filings"][0]["filing_price"], "15-17")
        self.assertEqual(payload["filings"][0]["filing_price_source"], existing_source)
        self.assertEqual((recovered, checked), (1, 1))


if __name__ == "__main__":
    unittest.main()

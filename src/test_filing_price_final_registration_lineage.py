import unittest

import filing_price_history


class FinalRegistrationFilingPriceLineageTests(unittest.TestCase):
    def _row(self, **overrides):
        row = {
            "id": "priced-final-lineage",
            "company": "Concurrent Registration Corp.",
            "ticker": "CRC",
            "cik": "0001234567",
            "accession_no": "0001234567-26-000090",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-08-30",
            "filing_date": "2026-08-01",
            "pricing_date": "2026-08-29",
            "offering_price": 16.0,
            "filing_price": None,
        }
        row.update(overrides)
        return row

    def test_final_424b4_file_number_beats_newer_unrelated_s1_registration(self):
        history = [
            {
                "form_type": "S-1/A",
                "accession_no": "0001234567-26-000089",
                "filing_date": "2026-08-28",
                "file_number": "333-999999",
            },
            {
                "form_type": "S-1/A",
                "accession_no": "0001234567-26-000080",
                "filing_date": "2026-08-25",
                "file_number": "333-888888",
            },
            {
                "form_type": "S-1",
                "accession_no": "0001234567-26-000060",
                "filing_date": "2026-08-01",
                "file_number": "333-888888",
            },
        ]
        calls = []
        final_calls = []

        def registration_loader(cik, metadata):
            calls.append(metadata["accession_no"])
            if metadata["file_number"] == "333-999999":
                raise AssertionError("unrelated newer registration must not be inspected")
            if metadata["accession_no"] == "0001234567-26-000080":
                return (
                    {"price_range": {"range_low": 15, "range_high": 17}},
                    "https://www.sec.gov/Archives/edgar/data/1234567/000123456726000080/0001234567-26-000080-index.htm",
                )
            return (
                {"price_range": {"range_low": None, "range_high": None}},
                "https://www.sec.gov/Archives/edgar/data/1234567/000123456726000060/0001234567-26-000060-index.htm",
            )

        def final_registration_loader(filing):
            final_calls.append(filing["accession_no"])
            return "333-888888"

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [self._row()]},
            history_loader=lambda cik, pricing_date: history,
            registration_loader=registration_loader,
            final_registration_loader=final_registration_loader,
        )

        row = payload["filings"][0]
        self.assertEqual(row["filing_price"], "15-17")
        self.assertEqual(row["price_range"], "15-17")
        self.assertEqual(
            row["filing_price_source"]["accession_no"],
            "0001234567-26-000080",
        )
        self.assertEqual(
            row["filing_price_source"]["file_number"],
            "333-888888",
        )
        self.assertEqual(calls, ["0001234567-26-000080"])
        self.assertEqual(final_calls, ["0001234567-26-000090"])
        self.assertEqual((recovered, checked), (1, 1))

    def test_required_final_file_number_absent_from_s1_history_fails_closed(self):
        history = [
            {
                "form_type": "S-1/A",
                "accession_no": "0001234567-26-000089",
                "filing_date": "2026-08-28",
                "file_number": "333-999999",
            }
        ]

        with self.assertRaisesRegex(
            filing_price_history.FilingPriceHistoryError,
            "no S-1/S-1A history inside the current IPO registration",
        ):
            filing_price_history.recover_payload_filing_prices(
                {"filings": [self._row()]},
                history_loader=lambda cik, pricing_date: history,
                registration_loader=lambda *args: (_ for _ in ()).throw(
                    AssertionError("wrong registration must not be parsed")
                ),
                final_registration_loader=lambda filing: "333-888888",
            )

    def test_blank_cannot_be_accepted_when_final_lineage_cannot_be_established(self):
        with self.assertRaisesRegex(
            filing_price_history.FilingPriceHistoryError,
            "final lineage unavailable",
        ):
            filing_price_history.recover_payload_filing_prices(
                {"filings": [self._row()]},
                history_loader=lambda cik, pricing_date: [
                    {
                        "form_type": "S-1",
                        "accession_no": "0001234567-26-000060",
                        "filing_date": "2026-08-01",
                        "file_number": "333-888888",
                    }
                ],
                registration_loader=lambda *args: ({}, ""),
                final_registration_loader=lambda filing: (_ for _ in ()).throw(
                    RuntimeError("final lineage unavailable")
                ),
            )

    def test_exact_final_accession_loader_requires_424b4_file_number_and_date(self):
        row = self._row()
        calls = []

        def rows_loader(cik, required_accessions):
            calls.append((cik, required_accessions))
            return [
                {
                    "accession_no": row["accession_no"],
                    "form": "424B4",
                    "file_number": "333-888888",
                    "filing_date": row["filed"],
                }
            ]

        self.assertEqual(
            filing_price_history._final_registration_file_number(
                row,
                rows_loader=rows_loader,
            ),
            "333-888888",
        )
        self.assertEqual(
            calls,
            [("0001234567", ("000123456726000090",))],
        )

        with self.assertRaisesRegex(
            filing_price_history.FilingPriceHistoryError,
            "filing date does not match",
        ):
            filing_price_history._final_registration_file_number(
                row,
                rows_loader=lambda cik, required_accessions: [
                    {
                        "accession_no": row["accession_no"],
                        "form": "424B4",
                        "file_number": "333-888888",
                        "filing_date": "2026-08-31",
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()

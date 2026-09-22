import unittest

import filing_price_history


class FilingPriceCompactAcceptanceRegressionTests(unittest.TestCase):
    def _row(self):
        return {
            "id": "compact-acceptance-priced",
            "company": "Compact Acceptance IPO Corp.",
            "ticker": "CAIP",
            "cik": "0001234567",
            "accession_no": "0001234567-26-000100",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-09-10",
            "filing_date": "2026-09-01",
            "pricing_date": "2026-09-10",
            "offering_price": 18.0,
            "filing_price": None,
        }

    @staticmethod
    def _history():
        return [
            {
                "form_type": "S-1/A",
                "accession_no": "0001234567-26-000095",
                "filing_date": "2026-09-10",
                "file_number": "333-888888",
                "acceptance_datetime": "20260910110000",
            },
            {
                "form_type": "S-1/A",
                "accession_no": "0001234567-26-000080",
                "filing_date": "2026-09-09",
                "file_number": "333-888888",
                "acceptance_datetime": "20260909160000",
            },
        ]

    @staticmethod
    def _registration_loader(cik, metadata):
        values = {
            "0001234567-26-000095": (16, 18),
            "0001234567-26-000080": (15, 17),
        }
        low, high = values[metadata["accession_no"]]
        return (
            {"price_range": {"range_low": low, "range_high": high}},
            "https://www.sec.gov/Archives/edgar/data/1234567/"
            f"{metadata['accession_no']}/index.htm",
        )

    @staticmethod
    def _final_identity(acceptance_datetime):
        return filing_price_history._FinalRegistrationFileNumber(
            "333-888888",
            filing_date="2026-09-10",
            acceptance_datetime=acceptance_datetime,
        )

    def _recover(self, history, final_acceptance):
        return filing_price_history.recover_payload_filing_prices(
            {"filings": [self._row()]},
            history_loader=lambda _cik, _pricing_date: history,
            registration_loader=self._registration_loader,
            final_registration_loader=lambda _filing: self._final_identity(
                final_acceptance
            ),
        )

    def test_compact_edgar_time_before_final_keeps_same_day_amendment_eligible(self):
        payload, recovered, checked = self._recover(
            self._history(),
            "20260910120000",
        )

        row = payload["filings"][0]
        self.assertEqual(row["filing_price"], "16-18")
        self.assertEqual(
            row["filing_price_source"]["accession_no"],
            "0001234567-26-000095",
        )
        self.assertEqual((recovered, checked), (1, 1))

    def test_compact_edgar_time_after_final_is_not_preceding_history(self):
        history = self._history()
        history[0]["acceptance_datetime"] = "20260910130000"

        payload, _, _ = self._recover(history, "20260910120000")

        row = payload["filings"][0]
        self.assertEqual(row["filing_price"], "15-17")
        self.assertEqual(
            row["filing_price_source"]["accession_no"],
            "0001234567-26-000080",
        )

    def test_equal_compact_acceptance_times_fail_closed(self):
        with self.assertRaisesRegex(
            filing_price_history.FilingPriceHistoryError,
            "same-day S-1/424B4 order is ambiguous",
        ):
            self._recover(self._history(), "20260910110000")

    def test_malformed_compact_acceptance_time_fails_closed(self):
        history = self._history()
        history[0]["acceptance_datetime"] = "2026091011AB00"

        with self.assertRaisesRegex(
            filing_price_history.FilingPriceHistoryError,
            "acceptance time is missing or malformed",
        ):
            self._recover(history, "20260910120000")


if __name__ == "__main__":
    unittest.main()

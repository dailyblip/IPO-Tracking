import unittest
from unittest.mock import patch

import filing_price_history


class FilingPriceSameDayAcceptanceTests(unittest.TestCase):
    def _row(self):
        return {
            "id": "same-day-priced",
            "company": "Same Day IPO Corp.",
            "ticker": "SDIP",
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

    def _final_identity(self, acceptance_datetime):
        return filing_price_history._FinalRegistrationFileNumber(
            "333-888888",
            filing_date="2026-09-10",
            acceptance_datetime=acceptance_datetime,
        )

    @staticmethod
    def _registration_loader(cik, metadata):
        accession = metadata["accession_no"]
        values = {
            "0001234567-26-000080": (15, 17),
            "0001234567-26-000095": (16, 18),
            "0001234567-26-000105": (19, 21),
        }
        low, high = values[accession]
        return (
            {"price_range": {"range_low": low, "range_high": high}},
            f"https://www.sec.gov/Archives/edgar/data/1234567/{accession}/index.htm",
        )

    def test_same_day_s1_after_final_is_not_preceding_price_history(self):
        history = [
            {
                "form_type": "S-1/A",
                "accession_no": "0001234567-26-000105",
                "filing_date": "2026-09-10",
                "file_number": "333-888888",
                "acceptance_datetime": "2026-09-10T17:00:00Z",
            },
            {
                "form_type": "S-1/A",
                "accession_no": "0001234567-26-000080",
                "filing_date": "2026-09-09",
                "file_number": "333-888888",
                "acceptance_datetime": "2026-09-09T20:00:00Z",
            },
        ]

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [self._row()]},
            history_loader=lambda cik, pricing_date: history,
            registration_loader=self._registration_loader,
            final_registration_loader=lambda filing: self._final_identity(
                "2026-09-10T16:00:00Z"
            ),
        )

        row = payload["filings"][0]
        self.assertEqual(row["filing_price"], "15-17")
        self.assertEqual(
            row["filing_price_source"]["accession_no"],
            "0001234567-26-000080",
        )
        self.assertEqual((recovered, checked), (1, 1))

    def test_same_day_s1_before_final_remains_eligible(self):
        history = [
            {
                "form_type": "S-1/A",
                "accession_no": "0001234567-26-000095",
                "filing_date": "2026-09-10",
                "file_number": "333-888888",
                "acceptance_datetime": "2026-09-10T15:00:00Z",
            },
            {
                "form_type": "S-1/A",
                "accession_no": "0001234567-26-000080",
                "filing_date": "2026-09-09",
                "file_number": "333-888888",
                "acceptance_datetime": "2026-09-09T20:00:00Z",
            },
        ]

        payload, _, _ = filing_price_history.recover_payload_filing_prices(
            {"filings": [self._row()]},
            history_loader=lambda cik, pricing_date: history,
            registration_loader=self._registration_loader,
            final_registration_loader=lambda filing: self._final_identity(
                "2026-09-10T16:00:00Z"
            ),
        )

        row = payload["filings"][0]
        self.assertEqual(row["filing_price"], "16-18")
        self.assertEqual(
            row["filing_price_source"]["accession_no"],
            "0001234567-26-000095",
        )

    def test_equal_same_day_acceptance_times_fail_closed(self):
        history = [
            {
                "form_type": "S-1/A",
                "accession_no": "0001234567-26-000095",
                "filing_date": "2026-09-10",
                "file_number": "333-888888",
                "acceptance_datetime": "2026-09-10T16:00:00Z",
            }
        ]

        with self.assertRaisesRegex(
            filing_price_history.FilingPriceHistoryError,
            "same-day S-1/424B4 order is ambiguous",
        ):
            filing_price_history.recover_payload_filing_prices(
                {"filings": [self._row()]},
                history_loader=lambda cik, pricing_date: history,
                registration_loader=self._registration_loader,
                final_registration_loader=lambda filing: self._final_identity(
                    "2026-09-10T16:00:00Z"
                ),
            )

    def test_missing_same_day_acceptance_time_fails_closed(self):
        history = [
            {
                "form_type": "S-1/A",
                "accession_no": "0001234567-26-000095",
                "filing_date": "2026-09-10",
                "file_number": "333-888888",
                "acceptance_datetime": "",
            }
        ]

        with self.assertRaisesRegex(
            filing_price_history.FilingPriceHistoryError,
            "same-day S-1/424B4 order cannot be proven",
        ):
            filing_price_history.recover_payload_filing_prices(
                {"filings": [self._row()]},
                history_loader=lambda cik, pricing_date: history,
                registration_loader=self._registration_loader,
                final_registration_loader=lambda filing: self._final_identity(
                    "2026-09-10T16:00:00Z"
                ),
            )

    def test_sec_history_retains_acceptance_times_and_orders_same_day_filings(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["S-1/A", "S-1/A"],
                    "accessionNumber": [
                        "0001234567-26-000095",
                        "0001234567-26-000096",
                    ],
                    "filingDate": ["2026-09-10", "2026-09-10"],
                    "fileNumber": ["333-888888", "333-888888"],
                    "acceptanceDateTime": [
                        "2026-09-10T14:00:00Z",
                        "2026-09-10T15:00:00Z",
                    ],
                },
                "files": [],
            }
        }

        with patch.object(filing_price_history.edgar_client, "_get_headers", return_value={}), patch.object(
            filing_price_history.edgar_client,
            "_request_json",
            return_value=submissions,
        ):
            history = filing_price_history.sec_s1_history(
                "0001234567",
                "2026-09-10",
            )

        self.assertEqual(
            [item["accession_no"] for item in history],
            ["0001234567-26-000096", "0001234567-26-000095"],
        )
        self.assertEqual(
            history[0]["acceptance_datetime"],
            "2026-09-10T15:00:00Z",
        )


if __name__ == "__main__":
    unittest.main()

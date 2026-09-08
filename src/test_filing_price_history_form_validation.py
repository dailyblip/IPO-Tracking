import unittest
from unittest import mock

import filing_price_history


class FilingPriceHistoryFormValidationTests(unittest.TestCase):
    def _submissions(
        self,
        forms,
        *,
        accessions=None,
        filing_dates=None,
        file_numbers=None,
    ):
        count = len(forms)
        return {
            "filings": {
                "recent": {
                    "form": forms,
                    "accessionNumber": (
                        accessions
                        if accessions is not None
                        else [
                            "0001234567-26-000004",
                            "0001234567-26-000003",
                        ][:count]
                    ),
                    "filingDate": (
                        filing_dates
                        if filing_dates is not None
                        else ["2026-08-19", "2026-08-18"][:count]
                    ),
                    "fileNumber": (
                        file_numbers
                        if file_numbers is not None
                        else ["333-300001", "333-300001"][:count]
                    ),
                },
                "files": [],
            }
        }

    def _history(self, forms, **submission_overrides):
        with mock.patch.object(
            filing_price_history.edgar_client, "_get_headers", return_value={}
        ), mock.patch.object(
            filing_price_history.edgar_client,
            "_request_json",
            return_value=self._submissions(forms, **submission_overrides),
        ):
            return filing_price_history.sec_s1_history("1234567", "2026-08-20")

    def test_blank_form_metadata_fails_closed(self):
        with self.assertRaises(filing_price_history.FilingPriceHistoryError) as error:
            self._history(["", "S-1/A"])

        self.assertIn("malformed form metadata", str(error.exception))

    def test_non_string_form_metadata_fails_closed(self):
        with self.assertRaises(filing_price_history.FilingPriceHistoryError) as error:
            self._history([{"form": "S-1/A"}, "S-1/A"])

        self.assertIn("malformed form metadata", str(error.exception))

    def test_non_string_s1_accession_metadata_fails_closed(self):
        with self.assertRaises(filing_price_history.FilingPriceHistoryError) as error:
            self._history(
                ["8-K", "S-1/A"],
                accessions=["0001234567-26-000004", {"accession": "bad"}],
            )

        self.assertIn("malformed accession metadata", str(error.exception))

    def test_non_string_s1_filing_date_metadata_fails_closed(self):
        with self.assertRaises(filing_price_history.FilingPriceHistoryError) as error:
            self._history(
                ["8-K", "S-1/A"],
                filing_dates=["2026-08-19", 20260818],
            )

        self.assertIn("malformed filing-date metadata", str(error.exception))

    def test_non_string_s1_file_number_metadata_fails_closed(self):
        with self.assertRaises(filing_price_history.FilingPriceHistoryError) as error:
            self._history(
                ["8-K", "S-1/A"],
                file_numbers=["333-300001", 333300001],
            )

        self.assertIn("malformed file-number metadata", str(error.exception))

    def test_valid_non_s1_form_does_not_block_s1_history(self):
        history = self._history(["8-K", "S-1/A"])

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["form_type"], "S-1/A")
        self.assertEqual(history[0]["accession_no"], "0001234567-26-000003")


if __name__ == "__main__":
    unittest.main()

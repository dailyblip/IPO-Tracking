import unittest
from unittest import mock

import filing_price_history


class FilingPriceHistoryFormValidationTests(unittest.TestCase):
    def _submissions(self, forms):
        return {
            "filings": {
                "recent": {
                    "form": forms,
                    "accessionNumber": [
                        "0001234567-26-000004",
                        "0001234567-26-000003",
                    ][: len(forms)],
                    "filingDate": ["2026-08-19", "2026-08-18"][: len(forms)],
                    "fileNumber": ["333-300001", "333-300001"][: len(forms)],
                },
                "files": [],
            }
        }

    def _history(self, forms):
        with mock.patch.object(
            filing_price_history.edgar_client, "_get_headers", return_value={}
        ), mock.patch.object(
            filing_price_history.edgar_client,
            "_request_json",
            return_value=self._submissions(forms),
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

    def test_valid_non_s1_form_does_not_block_s1_history(self):
        history = self._history(["8-K", "S-1/A"])

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["form_type"], "S-1/A")
        self.assertEqual(history[0]["accession_no"], "0001234567-26-000003")


if __name__ == "__main__":
    unittest.main()

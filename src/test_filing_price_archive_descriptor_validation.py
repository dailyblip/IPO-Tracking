import unittest
from unittest import mock

import filing_price_history


class FilingPriceArchiveDescriptorValidationTests(unittest.TestCase):
    def submissions_with_invalid_filing_from(self):
        return {
            "filings": {
                "recent": {
                    "form": ["S-1/A"],
                    "accessionNumber": ["0001234567-26-000003"],
                    "filingDate": ["2026-08-18"],
                    "fileNumber": ["333-300001"],
                },
                "files": [
                    {
                        "name": "CIK0001234567-submissions-001.json",
                        "filingFrom": "2026-08-XX",
                        "filingTo": "2026-08-10",
                    }
                ],
            }
        }

    def priced_row(self):
        return {
            "id": "priced-invalid-archive-descriptor",
            "company": "Descriptor Corp.",
            "ticker": "DSC",
            "cik": "1234567",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-08-20",
            "filing_date": "2026-08-01",
            "pricing_date": "2026-08-20",
            "offering_price": 17.0,
            "filing_price": None,
        }

    def test_invalid_archive_filing_from_fails_closed_before_archive_fetch(self):
        calls = []

        def request_json(url, headers):
            calls.append(url)
            if url.endswith("CIK0001234567.json"):
                return self.submissions_with_invalid_filing_from()
            raise AssertionError(f"archive should not be fetched after malformed filingFrom: {url}")

        with mock.patch.object(filing_price_history.edgar_client, "_get_headers", return_value={}), mock.patch.object(
            filing_price_history.edgar_client,
            "_request_json",
            side_effect=request_json,
        ):
            with self.assertRaisesRegex(
                filing_price_history.FilingPriceHistoryError,
                "invalid archive filingFrom",
            ):
                filing_price_history.sec_s1_history("1234567", "2026-08-20")

        self.assertEqual(len(calls), 1)

    def test_blank_priced_row_cannot_accept_malformed_archive_chronology(self):
        def request_json(url, headers):
            if url.endswith("CIK0001234567.json"):
                return self.submissions_with_invalid_filing_from()
            raise AssertionError(f"archive should not be fetched after malformed filingFrom: {url}")

        with mock.patch.object(filing_price_history.edgar_client, "_get_headers", return_value={}), mock.patch.object(
            filing_price_history.edgar_client,
            "_request_json",
            side_effect=request_json,
        ):
            with self.assertRaisesRegex(
                filing_price_history.FilingPriceHistoryError,
                "invalid archive filingFrom",
            ):
                filing_price_history.recover_payload_filing_prices(
                    {"filings": [self.priced_row()]},
                    registration_loader=lambda cik, metadata: (
                        {"price_range": {"range_low": None, "range_high": None}},
                        "https://www.sec.gov/no-range",
                    ),
                )


if __name__ == "__main__":
    unittest.main()

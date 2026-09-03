import unittest
from unittest import mock

import filing_price_history


class ArchivedFilingPriceHistoryTests(unittest.TestCase):
    def priced_row(self):
        return {
            "id": "final-archived",
            "company": "Archived Range Corp.",
            "ticker": "ARC",
            "cik": "1234567",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-08-20",
            "filing_date": "2026-08-01",
            "pricing_date": "2026-08-20",
            "offering_price": 17.0,
            "filing_price": None,
        }

    def submissions(self):
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
                        "filingFrom": "2026-08-01",
                        "filingTo": "2026-08-10",
                    },
                    {
                        "name": "CIK0001234567-submissions-002.json",
                        "filingFrom": "2026-08-21",
                        "filingTo": "2026-08-25",
                    },
                ],
            }
        }

    def archive(self):
        return {
            "form": ["S-1"],
            "accessionNumber": ["0001234567-26-000001"],
            "filingDate": ["2026-08-01"],
            "fileNumber": ["333-300001"],
        }

    def test_sec_history_merges_relevant_archived_s1_metadata(self):
        calls = []

        def request_json(url, headers):
            calls.append(url)
            if url.endswith("CIK0001234567.json"):
                return self.submissions()
            if url.endswith("CIK0001234567-submissions-001.json"):
                return self.archive()
            raise AssertionError(f"unexpected SEC request: {url}")

        with mock.patch.object(filing_price_history.edgar_client, "_get_headers", return_value={}), mock.patch.object(
            filing_price_history.edgar_client,
            "_request_json",
            side_effect=request_json,
        ):
            history = filing_price_history.sec_s1_history("1234567", "2026-08-20")

        self.assertEqual(
            [item["accession_no"] for item in history],
            ["0001234567-26-000003", "0001234567-26-000001"],
        )
        self.assertEqual(history[1]["file_number"], "333-300001")
        self.assertTrue(any(url.endswith("submissions-001.json") for url in calls))
        self.assertFalse(any(url.endswith("submissions-002.json") for url in calls))

    def test_blank_priced_row_recovers_range_found_only_in_archive(self):
        def request_json(url, headers):
            if url.endswith("CIK0001234567.json"):
                return self.submissions()
            if url.endswith("CIK0001234567-submissions-001.json"):
                return self.archive()
            raise AssertionError(f"unexpected SEC request: {url}")

        inspected = []

        def registration_loader(cik, metadata):
            inspected.append(metadata["accession_no"])
            if metadata["accession_no"] == "0001234567-26-000003":
                return {
                    "price_range": {"range_low": None, "range_high": None}
                }, "https://www.sec.gov/amendment"
            return {
                "price_range": {"range_low": 14.0, "range_high": 16.0}
            }, "https://www.sec.gov/archived-initial"

        with mock.patch.object(filing_price_history.edgar_client, "_get_headers", return_value={}), mock.patch.object(
            filing_price_history.edgar_client,
            "_request_json",
            side_effect=request_json,
        ):
            payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
                {"filings": [self.priced_row()]},
                registration_loader=registration_loader,
            )

        filing = payload["filings"][0]
        self.assertEqual(
            inspected,
            ["0001234567-26-000003", "0001234567-26-000001"],
        )
        self.assertEqual(filing["filing_price"], "14-16")
        self.assertEqual(filing["price_range"], "14-16")
        self.assertEqual(
            filing["filing_price_source"]["accession_no"],
            "0001234567-26-000001",
        )
        self.assertEqual((recovered, checked), (1, 1))

    def test_archive_lookup_failure_blocks_blank_acceptance(self):
        def request_json(url, headers):
            if url.endswith("CIK0001234567.json"):
                return self.submissions()
            if url.endswith("CIK0001234567-submissions-001.json"):
                raise RuntimeError("archive unavailable")
            raise AssertionError(f"unexpected SEC request: {url}")

        with mock.patch.object(filing_price_history.edgar_client, "_get_headers", return_value={}), mock.patch.object(
            filing_price_history.edgar_client,
            "_request_json",
            side_effect=request_json,
        ):
            with self.assertRaises(filing_price_history.FilingPriceHistoryError) as error:
                filing_price_history.recover_payload_filing_prices(
                    {"filings": [self.priced_row()]},
                    registration_loader=lambda cik, metadata: (
                        {"price_range": {"range_low": None, "range_high": None}},
                        "https://www.sec.gov/no-range",
                    ),
                )

        self.assertIn("submissions archive", str(error.exception))
        self.assertIn("archive unavailable", str(error.exception))


if __name__ == "__main__":
    unittest.main()

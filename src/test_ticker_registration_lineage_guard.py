import unittest
from unittest.mock import patch

import ticker_listing_reconciler as reconciler


class TickerRegistrationLineageGuardTests(unittest.TestCase):
    def test_different_registration_file_number_cannot_seed_later_ticker(self):
        payload = {
            "filings": [
                {
                    "id": "new-registration",
                    "accession_no": "0000000000-26-000200",
                    "company": "Returning Issuer, Inc.",
                    "cik": "0001234567",
                    "ticker": "OLD",
                    "form": "S-1/A",
                    "filed": "2026-09-08",
                    "sec_url": "https://www.sec.gov/new-registration-index.htm",
                    "_registration_file_number": "333-NEW",
                },
                {
                    "id": "old-registration",
                    "accession_no": "0000000000-26-000100",
                    "company": "Returning Issuer, Inc.",
                    "cik": "0001234567",
                    "ticker": "OLD",
                    "form": "S-1",
                    "filed": "2026-08-01",
                    "sec_url": "https://www.sec.gov/old-registration-index.htm",
                    "_registration_file_number": "333-OLD",
                },
            ]
        }
        texts = {
            "new-registration": "This amendment does not repeat listing terms.",
            "old-registration": (
                "We have applied to list our common stock on Nasdaq under the symbol OLD."
            ),
        }

        updated, conflicts = reconciler.reconcile_payload(
            payload, fetch_text=lambda record: texts[record["id"]]
        )

        self.assertEqual((updated, conflicts), (1, 0))
        self.assertEqual(payload["filings"][0]["ticker"], "")
        self.assertEqual(payload["filings"][1]["ticker"], "OLD")

    def test_same_registration_file_number_can_seed_later_amendment(self):
        payload = {
            "filings": [
                {
                    "id": "amendment",
                    "accession_no": "0001628280-26-060761",
                    "company": "SB Energy, Inc.",
                    "cik": "0002133037",
                    "ticker": "",
                    "form": "S-1/A",
                    "filed": "2026-09-04",
                    "sec_url": "https://www.sec.gov/amendment-index.htm",
                    "_registration_file_number": "333-99999",
                },
                {
                    "id": "initial",
                    "accession_no": "0001628280-26-059639",
                    "company": "SB Energy, Inc.",
                    "cik": "0002133037",
                    "ticker": "SBE",
                    "form": "S-1",
                    "filed": "2026-09-01",
                    "sec_url": "https://www.sec.gov/initial-index.htm",
                    "_registration_file_number": "333-99999",
                },
            ]
        }
        texts = {
            "amendment": "This amendment updates financial statements and risk factors.",
            "initial": (
                "We have applied to list our common stock on Nasdaq under the symbol SBE."
            ),
        }

        updated, conflicts = reconciler.reconcile_payload(
            payload, fetch_text=lambda record: texts[record["id"]]
        )

        self.assertEqual((updated, conflicts), (1, 0))
        self.assertEqual(payload["filings"][0]["ticker"], "SBE")

    def test_missing_current_file_number_fails_closed(self):
        payload = {
            "filings": [
                {
                    "id": "current",
                    "accession_no": "0000000000-26-000200",
                    "company": "Returning Issuer, Inc.",
                    "cik": "0001234567",
                    "ticker": "STALE",
                    "form": "S-1/A",
                    "filed": "2026-09-08",
                    "sec_url": "https://www.sec.gov/current-index.htm",
                    "_registration_file_number": "",
                },
                {
                    "id": "prior",
                    "accession_no": "0000000000-26-000100",
                    "company": "Returning Issuer, Inc.",
                    "cik": "0001234567",
                    "ticker": "SBE",
                    "form": "S-1",
                    "filed": "2026-09-01",
                    "sec_url": "https://www.sec.gov/prior-index.htm",
                    "_registration_file_number": "333-99999",
                },
            ]
        }
        texts = {
            "current": "This amendment does not repeat listing terms.",
            "prior": "We have applied to list our common stock on Nasdaq under the symbol SBE.",
        }

        updated, conflicts = reconciler.reconcile_payload(
            payload, fetch_text=lambda record: texts[record["id"]]
        )

        self.assertEqual((updated, conflicts), (1, 0))
        self.assertEqual(payload["filings"][0]["ticker"], "")

    def test_sec_submission_file_numbers_request_exact_accessions_from_archive_loader(self):
        records = [
            {
                "accession_no": "0001628280-26-060761",
                "cik": "0002133037",
                "form": "S-1/A",
            },
            {
                "accession_no": "0001628280-26-059639",
                "cik": "0002133037",
                "form": "S-1",
            },
        ]
        submission_rows = [
            {
                "accession_no": "0001628280-26-060761",
                "form": "S-1/A",
                "file_number": "333-99999",
                "filing_date": "2026-09-04",
                "primary_document": "amendment.htm",
            },
            {
                "accession_no": "0001628280-26-059639",
                "form": "S-1",
                "file_number": "333-99999",
                "filing_date": "2026-09-01",
                "primary_document": "initial.htm",
            },
        ]

        with patch.object(
            reconciler.registration_lineage,
            "load_registration_rows",
            return_value=submission_rows,
        ) as lineage_rows:
            lineage = reconciler._registration_file_numbers(records)

        self.assertEqual(
            lineage,
            {
                ("0002133037", "0001628280-26-060761"): "333-99999",
                ("0002133037", "0001628280-26-059639"): "333-99999",
            },
        )
        lineage_rows.assert_called_once_with(
            "0002133037",
            ("000162828026060761", "000162828026059639"),
        )


if __name__ == "__main__":
    unittest.main()

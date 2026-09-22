import unittest
from unittest.mock import patch

import s1_registration_history_gate as gate


class SameDayRegistrationHistoryGuardTests(unittest.TestCase):
    def test_same_day_s1_is_not_treated_as_predecessor_without_acceptance_time(self):
        rows = [
            {
                "accession_no": "0000000000-26-000300",
                "form": "S-1/A",
                "file_number": "333-300000",
                "filing_date": "2026-09-09",
                "primary_document": "current.htm",
            },
            {
                "accession_no": "0000000000-26-000299",
                "form": "S-1",
                "file_number": "333-300000",
                "filing_date": "2026-09-09",
                "primary_document": "same-day.htm",
            },
            {
                "accession_no": "0000000000-26-000250",
                "form": "S-1",
                "file_number": "333-300000",
                "filing_date": "2026-09-08",
                "primary_document": "prior-day.htm",
            },
        ]

        with patch.object(gate, "_recent_submission_rows", return_value=rows):
            predecessors = gate._same_registration_predecessors(
                "0002000300", "0000000000-26-000300"
            )

        self.assertEqual(
            ["0000000000-26-000250"],
            [row["accession_no"] for row in predecessors],
        )

    def test_proven_earlier_same_day_s1_is_predecessor(self):
        rows = [
            {
                "accession_no": "0000000000-26-000300",
                "form": "S-1/A",
                "file_number": "333-300000",
                "filing_date": "2026-09-09",
                "acceptance_datetime": "20260909160000",  # 20:00 UTC
                "primary_document": "current.htm",
            },
            {
                "accession_no": "0000000000-26-000299",
                "form": "S-1",
                "file_number": "333-300000",
                "filing_date": "2026-09-09",
                "acceptance_datetime": "2026-09-09T19:00:00Z",
                "primary_document": "same-day-prior.htm",
            },
        ]

        with patch.object(gate, "_recent_submission_rows", return_value=rows):
            predecessors = gate._same_registration_predecessors(
                "0002000300", "0000000000-26-000300"
            )

        self.assertEqual(
            ["0000000000-26-000299"],
            [row["accession_no"] for row in predecessors],
        )

    def test_equal_later_or_ambiguous_same_day_s1_fails_closed(self):
        current = {
            "accession_no": "0000000000-26-000300",
            "form": "S-1/A",
            "file_number": "333-300000",
            "filing_date": "2026-09-09",
            "acceptance_datetime": "2026-09-09T20:00:00Z",
            "primary_document": "current.htm",
        }
        for acceptance in (
            "2026-09-09T20:00:00Z",
            "2026-09-09T20:01:00Z",
            "2026-09-09T19:00:00",
            "not-a-timestamp",
            "",
        ):
            prior = {
                "accession_no": "0000000000-26-000299",
                "form": "S-1",
                "file_number": "333-300000",
                "filing_date": "2026-09-09",
                "acceptance_datetime": acceptance,
                "primary_document": "same-day.htm",
            }
            with self.subTest(acceptance=acceptance), patch.object(
                gate, "_recent_submission_rows", return_value=[current, prior]
            ):
                predecessors = gate._same_registration_predecessors(
                    "0002000300", "0000000000-26-000300"
                )
            self.assertEqual([], predecessors)

    def test_missing_current_filing_date_fails_closed(self):
        rows = [
            {
                "accession_no": "0000000000-26-000300",
                "form": "S-1/A",
                "file_number": "333-300000",
                "filing_date": "",
                "primary_document": "current.htm",
            },
            {
                "accession_no": "0000000000-26-000250",
                "form": "S-1",
                "file_number": "333-300000",
                "filing_date": "2026-09-08",
                "primary_document": "prior.htm",
            },
        ]

        with patch.object(gate, "_recent_submission_rows", return_value=rows):
            predecessors = gate._same_registration_predecessors(
                "0002000300", "0000000000-26-000300"
            )

        self.assertEqual([], predecessors)

    def test_same_day_resale_language_cannot_seed_exclusion_without_order(self):
        record = {
            "company": "Same Day IPO, Inc.",
            "cik": "0002000300",
            "accession_no": "0000000000-26-000300",
            "form": "S-1/A",
            "stage": "Pre-pricing",
        }
        rows = [
            {
                "accession_no": "0000000000-26-000300",
                "form": "S-1/A",
                "file_number": "333-300000",
                "filing_date": "2026-09-09",
                "primary_document": "current.htm",
            },
            {
                "accession_no": "0000000000-26-000299",
                "form": "S-1",
                "file_number": "333-300000",
                "filing_date": "2026-09-09",
                "primary_document": "same-day-resale.htm",
            },
        ]

        with patch.object(gate, "_recent_submission_rows", return_value=rows), patch.object(
            gate.filing_parser, "fetch_document"
        ) as fetch_document:
            excluded = gate.amendment_inherits_resale_exclusion(record)

        self.assertFalse(excluded)
        fetch_document.assert_not_called()

    def test_same_day_reporting_history_requires_strict_acceptance_order(self):
        record = {
            "company": "Already Reporting Co",
            "cik": "0002000300",
            "accession_no": "0000000000-26-000300",
            "form": "S-1",
            "stage": "Pre-pricing",
        }
        current = {
            "accession_no": "0000000000-26-000300",
            "form": "S-1",
            "file_number": "333-300000",
            "filing_date": "2026-09-09",
            "acceptance_datetime": "20260909160000",  # 20:00 UTC
            "primary_document": "current.htm",
        }
        prior_reporting = {
            "accession_no": "0000000000-26-000298",
            "form": "8-K",
            "file_number": "001-40000",
            "filing_date": "2026-09-09",
            "acceptance_datetime": "2026-09-09T19:30:00Z",
            "primary_document": "report.htm",
        }

        with patch.object(
            gate, "_recent_submission_rows", return_value=[current, prior_reporting]
        ):
            self.assertTrue(gate.already_reporting_before_registration(record))

        prior_reporting["acceptance_datetime"] = "2026-09-09T20:00:00Z"
        with patch.object(
            gate, "_recent_submission_rows", return_value=[current, prior_reporting]
        ):
            self.assertFalse(gate.already_reporting_before_registration(record))

        prior_reporting["acceptance_datetime"] = "2026-09-09T20:30:00Z"
        with patch.object(
            gate, "_recent_submission_rows", return_value=[current, prior_reporting]
        ):
            self.assertFalse(gate.already_reporting_before_registration(record))

    def test_recent_submission_rows_keeps_rows_when_acceptance_metadata_is_absent(self):
        payload = {
            "filings": {
                "recent": {
                    "accessionNumber": ["0000000000-26-000300"],
                    "form": ["S-1"],
                    "fileNumber": ["333-300000"],
                    "filingDate": ["2026-09-09"],
                    "primaryDocument": ["current.htm"],
                }
            }
        }
        with patch.object(gate.edgar_client, "_request_json", return_value=payload), patch.object(
            gate.edgar_client, "_get_headers", return_value={"User-Agent": "test"}
        ):
            rows = gate._recent_submission_rows("0002000300")

        self.assertEqual(1, len(rows))
        self.assertEqual("", rows[0]["acceptance_datetime"])


if __name__ == "__main__":
    unittest.main()

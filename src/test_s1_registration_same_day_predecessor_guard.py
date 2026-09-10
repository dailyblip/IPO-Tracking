import unittest
from unittest.mock import patch

import s1_registration_history_gate as gate


class SameDayRegistrationHistoryGuardTests(unittest.TestCase):
    def test_same_day_s1_is_not_treated_as_predecessor(self):
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

    def test_same_day_resale_language_cannot_seed_exclusion(self):
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


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

import s1_registration_history_gate as gate


class S1AuthoritativeReportingCutoffTests(unittest.TestCase):
    def _record(self, filed="2026-09-10"):
        return {
            "company": "Chronology Test Co",
            "cik": "0002123456",
            "accession_no": "0002123456-26-000100",
            "form": "S-1",
            "stage": "Pre-pricing",
            "filed": filed,
        }

    def test_sec_candidate_date_prevents_false_reporting_exclusion(self):
        rows = [
            {
                "accession_no": "0002123456-26-000100",
                "form": "S-1",
                "file_number": "333-300001",
                "filing_date": "2026-09-05",
                "primary_document": "s1.htm",
            },
            {
                "accession_no": "0002123456-26-000110",
                "form": "8-K",
                "file_number": "001-50001",
                "filing_date": "2026-09-08",
                "primary_document": "8k.htm",
            },
        ]
        with patch.object(gate, "_recent_submission_rows", return_value=rows):
            self.assertFalse(gate.already_reporting_before_registration(self._record()))

    def test_sec_candidate_date_recovers_prior_reporting_when_feed_date_is_stale(self):
        rows = [
            {
                "accession_no": "0002123456-26-000100",
                "form": "S-1",
                "file_number": "333-300001",
                "filing_date": "2026-09-05",
                "primary_document": "s1.htm",
            },
            {
                "accession_no": "0002123456-26-000090",
                "form": "8-K",
                "file_number": "001-50001",
                "filing_date": "2026-09-02",
                "primary_document": "8k.htm",
            },
        ]
        with patch.object(gate, "_recent_submission_rows", return_value=rows):
            self.assertTrue(
                gate.already_reporting_before_registration(
                    self._record(filed="2026-09-01")
                )
            )

    def test_missing_exact_candidate_accession_does_not_guess_cutoff(self):
        rows = [
            {
                "accession_no": "0002123456-26-000099",
                "form": "S-1",
                "file_number": "333-300001",
                "filing_date": "2026-09-04",
                "primary_document": "other-s1.htm",
            },
            {
                "accession_no": "0002123456-26-000090",
                "form": "8-K",
                "file_number": "001-50001",
                "filing_date": "2026-09-02",
                "primary_document": "8k.htm",
            },
        ]
        with patch.object(gate, "_recent_submission_rows", return_value=rows):
            self.assertFalse(gate.already_reporting_before_registration(self._record()))

    def test_malformed_predecessor_date_cannot_seed_resale_history(self):
        payload = {
            "filings": {
                "recent": {
                    "accessionNumber": [
                        "0002123456-26-000100",
                        "0002123456-26-000090",
                    ],
                    "form": ["S-1/A", "S-1"],
                    "fileNumber": ["333-300001", "333-300001"],
                    "filingDate": ["2026-09-05", "2026-9-4"],
                    "primaryDocument": ["current.htm", "prior.htm"],
                }
            }
        }
        with patch.object(gate.edgar_client, "_request_json", return_value=payload), patch.object(
            gate.edgar_client, "_get_headers", return_value={"User-Agent": "test"}
        ):
            predecessors = gate._same_registration_predecessors(
                "2123456", "0002123456-26-000100"
            )
        self.assertEqual([], predecessors)


if __name__ == "__main__":
    unittest.main()

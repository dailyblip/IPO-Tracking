import unittest

import archived_reporting_history_gate as gate


class ArchivedReportingHistoryFormValidationTests(unittest.TestCase):
    @staticmethod
    def _submissions():
        return {
            "filings": {
                "recent": {
                    "form": ["424B4"],
                    "filingDate": ["2026-09-01"],
                },
                "files": [
                    {
                        "name": "CIK0000000001-submissions-001.json",
                        "filingFrom": "2020-01-01",
                        "filingTo": "2025-12-31",
                    }
                ],
            }
        }

    def test_non_string_recent_form_fails_closed(self):
        submissions = self._submissions()
        submissions["filings"]["recent"] = {
            "form": [{"unexpected": "8-K"}],
            "filingDate": ["2025-12-31"],
        }

        with self.assertRaises(gate.ArchivedReportingHistoryError):
            gate.has_prior_reporting_history(
                submissions,
                "2026-09-01",
                archive_loader=lambda _name: self.fail("archive should not be reached"),
            )

    def test_blank_archive_form_fails_closed(self):
        submissions = self._submissions()
        archived = {
            "form": ["   "],
            "filingDate": ["2025-04-10"],
        }

        with self.assertRaises(gate.ArchivedReportingHistoryError):
            gate.has_prior_reporting_history(
                submissions,
                "2026-09-01",
                archive_loader=lambda _name: archived,
            )

    def test_invalid_recent_filing_date_fails_closed(self):
        submissions = self._submissions()
        submissions["filings"]["recent"] = {
            "form": ["8-K"],
            "filingDate": ["not-a-date"],
        }

        with self.assertRaises(gate.ArchivedReportingHistoryError):
            gate.has_prior_reporting_history(
                submissions,
                "2026-09-01",
                archive_loader=lambda _name: self.fail("archive should not be reached"),
            )

    def test_malformed_recent_form_blocks_final_release(self):
        queue = {
            "filings": [
                {
                    "id": "final-malformed-form-history",
                    "company": "Malformed Form History Co",
                    "cik": "1",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-09-02",
                    "pricing_date": "2026-09-01",
                }
            ]
        }
        submissions = self._submissions()
        submissions["filings"]["recent"] = {
            "form": [{"unexpected": "10-K"}],
            "filingDate": ["2025-12-31"],
        }

        with self.assertRaises(gate.ArchivedReportingHistoryError):
            gate.sanitize_payloads(
                {"filings": []},
                queue,
                submissions_loader=lambda _cik: submissions,
                archive_loader=lambda _name: self.fail("archive should not be reached"),
            )


if __name__ == "__main__":
    unittest.main()

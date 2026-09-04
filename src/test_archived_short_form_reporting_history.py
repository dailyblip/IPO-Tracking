import unittest

import archived_reporting_history_gate as gate


class ArchivedShortFormReportingHistoryTests(unittest.TestCase):
    def test_archived_s3_f3_forms_are_prior_reporting_evidence(self):
        submissions = {
            "filings": {
                "recent": {"form": ["424B4"], "filingDate": ["2026-09-01"]},
                "files": [
                    {
                        "name": "CIK0000000001-submissions-001.json",
                        "filingFrom": "2020-01-01",
                    }
                ],
            }
        }
        for form in ("S-3", "S-3/A", "F-3", "F-3/A"):
            with self.subTest(form=form):
                archived = {"form": [form], "filingDate": ["2025-05-14"]}
                self.assertTrue(
                    gate.has_prior_reporting_history(
                        submissions,
                        "2026-09-01",
                        archive_loader=lambda _name, payload=archived: payload,
                    )
                )

    def test_same_day_archived_short_form_does_not_guess_event_order(self):
        submissions = {
            "filings": {
                "recent": {"form": ["424B4"], "filingDate": ["2026-09-01"]},
                "files": [{"name": "CIK0000000001-submissions-001.json"}],
            }
        }
        for form in ("S-3", "F-3"):
            with self.subTest(form=form):
                archived = {"form": [form], "filingDate": ["2026-09-01"]}
                self.assertFalse(
                    gate.has_prior_reporting_history(
                        submissions,
                        "2026-09-01",
                        archive_loader=lambda _name, payload=archived: payload,
                    )
                )

    def test_archived_short_form_removes_false_final_ipo_candidate(self):
        queue = {
            "filings": [
                {
                    "id": "final-followon",
                    "company": "Already Public Co",
                    "cik": "1",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-09-02",
                    "pricing_date": "2026-09-01",
                }
            ]
        }
        submissions = {
            "filings": {
                "recent": {"form": ["424B4"], "filingDate": ["2026-09-02"]},
                "files": [
                    {
                        "name": "CIK0000000001-submissions-001.json",
                        "filingFrom": "2020-01-01",
                    }
                ],
            }
        }
        archived = {"form": ["F-3/A"], "filingDate": ["2025-05-14"]}

        _, updated_queue, excluded_s1, excluded_final = gate.sanitize_payloads(
            {"filings": []},
            queue,
            submissions_loader=lambda _cik: submissions,
            archive_loader=lambda _name: archived,
        )

        self.assertEqual(set(), excluded_s1)
        self.assertEqual(1, len(excluded_final))
        self.assertEqual([], updated_queue["filings"])


if __name__ == "__main__":
    unittest.main()

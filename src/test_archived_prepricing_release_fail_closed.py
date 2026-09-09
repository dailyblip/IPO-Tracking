import unittest

import archived_reporting_history_gate as gate


class ArchivedPrepricingReleaseFailClosedTests(unittest.TestCase):
    def test_release_mode_blocks_prepricing_when_archived_history_cannot_be_checked(self):
        watch = {
            "filings": [
                {
                    "id": "s1-archive-unavailable",
                    "company": "Archive Review Required Co",
                    "cik": "1",
                    "form": "S-1",
                    "stage": "Pre-pricing",
                    "filed": "2026-09-01",
                }
            ]
        }
        queue = {"filings": list(watch["filings"])}
        submissions = {
            "filings": {
                "recent": {"form": ["S-1"], "filingDate": ["2026-09-01"]},
                "files": [{"name": "CIK0000000001-submissions-001.json"}],
            }
        }

        with self.assertRaisesRegex(
            gate.ArchivedReportingHistoryError,
            "Could not complete historical SEC reporting review",
        ):
            gate.sanitize_payloads(
                watch,
                queue,
                submissions_loader=lambda _cik: submissions,
                archive_loader=lambda _name: (_ for _ in ()).throw(
                    RuntimeError("SEC archive unavailable")
                ),
                fail_closed_prepricing=True,
            )

    def test_nonrelease_helper_can_still_leave_partial_fixture_unclassified(self):
        watch = {
            "filings": [
                {
                    "id": "s1-partial-fixture",
                    "company": "Partial Fixture Co",
                    "cik": "1",
                    "form": "S-1",
                    "stage": "Pre-pricing",
                    "filed": "2026-09-01",
                }
            ]
        }
        queue = {"filings": list(watch["filings"])}
        submissions = {
            "filings": {
                "recent": {"form": ["S-1"], "filingDate": ["2026-09-01"]},
                "files": [{"name": "CIK0000000001-submissions-001.json"}],
            }
        }

        updated_watch, updated_queue, excluded_s1, excluded_final = gate.sanitize_payloads(
            watch,
            queue,
            submissions_loader=lambda _cik: submissions,
            archive_loader=lambda _name: (_ for _ in ()).throw(
                RuntimeError("fixture has no archive")
            ),
        )

        self.assertEqual(set(), excluded_s1)
        self.assertEqual(set(), excluded_final)
        self.assertEqual(watch, updated_watch)
        self.assertEqual(queue, updated_queue)


if __name__ == "__main__":
    unittest.main()

import unittest

import archived_reporting_history_gate as gate


class S8ReportingHistoryTests(unittest.TestCase):
    def test_recent_s8_history_proves_prior_reporting(self):
        for form in ("S-8", "S-8 POS"):
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form, "S-1"],
                            "filingDate": ["2026-05-14", "2026-09-01"],
                        },
                        "files": [],
                    }
                }
                self.assertTrue(
                    gate.has_prior_reporting_history(submissions, "2026-09-01")
                )

    def test_archived_s8_history_proves_prior_reporting(self):
        submissions = {
            "filings": {
                "recent": {"form": ["S-1"], "filingDate": ["2026-09-01"]},
                "files": [
                    {
                        "name": "CIK0000000001-submissions-001.json",
                        "filingFrom": "2020-01-01",
                        "filingTo": "2025-12-31",
                    }
                ],
            }
        }
        for form in ("S-8", "S-8 POS"):
            with self.subTest(form=form):
                archived = {"form": [form], "filingDate": ["2025-05-14"]}
                self.assertTrue(
                    gate.has_prior_reporting_history(
                        submissions,
                        "2026-09-01",
                        archive_loader=lambda _name, archived=archived: archived,
                    )
                )

    def test_same_day_s8_does_not_infer_order(self):
        for form in ("S-8", "S-8 POS"):
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form, "S-1"],
                            "filingDate": ["2026-09-01", "2026-09-01"],
                        },
                        "files": [],
                    }
                }
                self.assertFalse(
                    gate.has_prior_reporting_history(submissions, "2026-09-01")
                )


if __name__ == "__main__":
    unittest.main()

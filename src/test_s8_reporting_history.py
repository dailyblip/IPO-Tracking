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

    def test_ipo_contemporaneous_s8_after_s1_does_not_reclassify_final_424b4(self):
        for form in ("S-8", "S-8 POS"):
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form, "S-1/A", "S-1", "424B4"],
                            "filingDate": [
                                "2026-06-03",
                                "2026-06-02",
                                "2026-05-15",
                                "2026-06-04",
                            ],
                        },
                        "files": [],
                    }
                }
                self.assertFalse(
                    gate.has_prior_reporting_history(submissions, "2026-06-04")
                )

    def test_s8_before_current_s1_sequence_still_proves_prior_reporting_for_final(self):
        for form in ("S-8", "S-8 POS"):
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form, "S-1/A", "S-1", "424B4"],
                            "filingDate": [
                                "2026-05-14",
                                "2026-06-02",
                                "2026-05-15",
                                "2026-06-04",
                            ],
                        },
                        "files": [],
                    }
                }
                self.assertTrue(
                    gate.has_prior_reporting_history(submissions, "2026-06-04")
                )

    def test_non_s8_reporting_form_between_s1_and_424b4_still_proves_prior_reporting(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["8-K", "S-1/A", "S-1", "424B4"],
                    "filingDate": [
                        "2026-06-03",
                        "2026-06-02",
                        "2026-05-15",
                        "2026-06-04",
                    ],
                },
                "files": [],
            }
        }
        self.assertTrue(
            gate.has_prior_reporting_history(submissions, "2026-06-04")
        )


if __name__ == "__main__":
    unittest.main()

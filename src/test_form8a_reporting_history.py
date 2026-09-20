import unittest

import archived_reporting_history_gate as gate


class Form8AReportingHistoryTests(unittest.TestCase):
    FORMS = ("8-A12B", "8-A12B/A", "8-A12G", "8-A12G/A")

    def test_form8a_before_current_s1_sequence_proves_prior_reporting(self):
        for form in self.FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form, "S-1", "424B4"],
                            "filingDate": [
                                "2026-05-14",
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

    def test_ipo_contemporaneous_form8a_after_s1_does_not_reclassify_final(self):
        for form in self.FORMS:
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

    def test_archived_form8a_before_s1_proves_prior_reporting(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["S-1"],
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
        for form in self.FORMS:
            with self.subTest(form=form):
                archived = {"form": [form], "filingDate": ["2025-05-14"]}
                self.assertTrue(
                    gate.has_prior_reporting_history(
                        submissions,
                        "2026-09-01",
                        archive_loader=lambda _name, archived=archived: archived,
                    )
                )

    def test_exact_registration_lineage_ignores_concurrent_s1_for_8a_cutoff(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["8-A12B", "S-1", "S-1", "424B4"],
                    "filingDate": [
                        "2026-05-20",
                        "2026-05-01",
                        "2026-06-01",
                        "2026-06-10",
                    ],
                    "accessionNumber": [
                        "0000000000-26-000050",
                        "0000000000-26-000040",
                        "0000000000-26-000080",
                        "0000000000-26-000100",
                    ],
                    "fileNumber": [
                        "001-99999",
                        "333-100000",
                        "333-200000",
                        "333-100000",
                    ],
                },
                "files": [],
            }
        }

        self.assertFalse(
            gate.has_prior_reporting_history(
                submissions,
                "2026-06-10",
                candidate_accession="0000000000-26-000100",
            )
        )


if __name__ == "__main__":
    unittest.main()

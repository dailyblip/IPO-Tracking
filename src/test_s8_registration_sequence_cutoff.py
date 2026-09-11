"""Regression coverage for IPO-contemporaneous S-8 chronology."""

import unittest

import archived_reporting_history_gate as gate


class S8RegistrationSequenceCutoffTests(unittest.TestCase):
    def test_s8_after_initial_s1_but_before_amendment_is_not_prior_reporting(self):
        for form in ("S-8", "S-8 POS"):
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form, "S-1/A", "S-1", "424B4"],
                            "filingDate": [
                                "2026-05-20",
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

    def test_exact_candidate_lineage_ignores_later_unrelated_s1(self):
        submissions = {
            "filings": {
                "recent": {
                    "accessionNumber": [
                        "0000000000-26-000003",
                        "0000000000-26-000002",
                        "0000000000-26-000001",
                        "0000000000-26-000004",
                    ],
                    "form": ["S-8", "S-1", "S-1", "424B4"],
                    "fileNumber": [
                        "333-300003",
                        "333-200002",
                        "333-100001",
                        "333-100001",
                    ],
                    "filingDate": [
                        "2026-07-15",
                        "2026-08-01",
                        "2026-07-01",
                        "2026-09-01",
                    ],
                },
                "files": [],
            }
        }

        self.assertFalse(
            gate.has_prior_reporting_history(
                submissions,
                "2026-09-01",
                candidate_accession="0000000000-26-000004",
            )
        )

    def test_exact_candidate_lineage_keeps_genuine_prior_s8(self):
        submissions = {
            "filings": {
                "recent": {
                    "accessionNumber": [
                        "0000000000-26-000003",
                        "0000000000-26-000002",
                        "0000000000-26-000001",
                        "0000000000-26-000004",
                    ],
                    "form": ["S-8", "S-1", "S-1", "424B4"],
                    "fileNumber": [
                        "333-300003",
                        "333-200002",
                        "333-100001",
                        "333-100001",
                    ],
                    "filingDate": [
                        "2026-06-20",
                        "2026-08-01",
                        "2026-07-01",
                        "2026-09-01",
                    ],
                },
                "files": [],
            }
        }

        self.assertTrue(
            gate.has_prior_reporting_history(
                submissions,
                "2026-09-01",
                candidate_accession="0000000000-26-000004",
            )
        )


if __name__ == "__main__":
    unittest.main()

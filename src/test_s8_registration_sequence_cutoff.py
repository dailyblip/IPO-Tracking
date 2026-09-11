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


if __name__ == "__main__":
    unittest.main()

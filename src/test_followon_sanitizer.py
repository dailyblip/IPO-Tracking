import unittest

import followon_sanitizer


class FollowOnSanitizerTests(unittest.TestCase):
    def test_prior_10q_proves_candidate_is_not_first_time_ipo(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["10-Q", "424B4"],
                    "filingDate": ["2026-05-14", "2026-06-01"],
                }
            }
        }
        self.assertTrue(
            followon_sanitizer.has_prior_periodic_report(submissions, "2026-06-01")
        )

    def test_prior_foreign_annual_report_proves_candidate_is_not_first_time_ipo(self):
        for form in ("20-F", "40-F"):
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form, "424B4"],
                            "filingDate": ["2026-05-14", "2026-06-01"],
                        }
                    }
                }
                self.assertTrue(
                    followon_sanitizer.has_prior_periodic_report(submissions, "2026-06-01")
                )

    def test_periodic_report_after_candidate_does_not_disqualify_historical_ipo(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["10-Q", "424B4"],
                    "filingDate": ["2026-08-20", "2026-08-07"],
                }
            }
        }
        self.assertFalse(
            followon_sanitizer.has_prior_periodic_report(submissions, "2026-08-07")
        )

    def test_payload_removes_proven_followon_but_keeps_prepricing_and_first_ipo(self):
        payload = {
            "schema_version": 1,
            "filings": [
                {
                    "id": "followon",
                    "company": "Already Public, Inc.",
                    "cik": "1",
                    "form": "424B4",
                    "filed": "2026-06-01",
                    "pricing_date": "2026-06-01",
                },
                {
                    "id": "foreign-followon",
                    "company": "Already Public Foreign Co.",
                    "cik": "4",
                    "form": "424B4",
                    "filed": "2026-06-01",
                    "pricing_date": "2026-06-01",
                },
                {
                    "id": "ipo",
                    "company": "New IPO, Inc.",
                    "cik": "2",
                    "form": "424B4",
                    "filed": "2026-08-07",
                    "pricing_date": "2026-08-07",
                },
                {
                    "id": "prepricing",
                    "company": "Pipeline Co",
                    "cik": "3",
                    "form": "S-1/A",
                    "filed": "2026-08-25",
                    "stage": "Pre-pricing",
                },
            ],
        }
        submissions = {
            "1": {
                "filings": {
                    "recent": {
                        "form": ["10-Q"],
                        "filingDate": ["2026-05-14"],
                    }
                }
            },
            "2": {
                "filings": {
                    "recent": {
                        "form": ["10-Q"],
                        "filingDate": ["2026-08-20"],
                    }
                }
            },
            "4": {
                "filings": {
                    "recent": {
                        "form": ["20-F"],
                        "filingDate": ["2026-05-14"],
                    }
                }
            },
        }

        updated, removed = followon_sanitizer.sanitize_payload(
            payload, submissions_loader=lambda cik: submissions[cik]
        )

        self.assertEqual(
            [item["id"] for item in removed],
            ["followon", "foreign-followon"],
        )
        self.assertEqual(
            [item["id"] for item in updated["filings"]],
            ["ipo", "prepricing"],
        )

    def test_missing_candidate_date_is_not_guessed(self):
        payload = {
            "filings": [
                {"id": "x", "company": "Unknown Date Co", "cik": "1", "form": "424B4"}
            ]
        }
        updated, removed = followon_sanitizer.sanitize_payload(
            payload, submissions_loader=lambda cik: self.fail("SEC lookup should not run")
        )
        self.assertIs(updated, payload)
        self.assertEqual(removed, [])


if __name__ == "__main__":
    unittest.main()

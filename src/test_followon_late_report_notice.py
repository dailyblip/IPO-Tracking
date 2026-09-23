import unittest

import followon_sanitizer


class FollowOnLateReportNoticeTests(unittest.TestCase):
    def test_prior_rule12b25_periodic_notice_proves_prior_reporting(self):
        for form in (
            "NT 10-Q",
            "NT 10-Q/A",
            "NT 10-K",
            "NT 10-K/A",
            "NT 20-F",
            "NT 20-F/A",
        ):
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
                    followon_sanitizer.has_prior_periodic_report(
                        submissions, "2026-06-01"
                    )
                )

    def test_rule12b25_notice_after_candidate_does_not_disqualify_historical_ipo(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["NT 10-Q", "424B4"],
                    "filingDate": ["2026-08-20", "2026-08-07"],
                }
            }
        }
        self.assertFalse(
            followon_sanitizer.has_prior_periodic_report(submissions, "2026-08-07")
        )


if __name__ == "__main__":
    unittest.main()

import unittest

import followon_sanitizer


class FollowOnProxyHistoryTests(unittest.TestCase):
    def test_prior_proxy_or_information_statement_proves_prior_reporting(self):
        for form in ("PRE 14A", "DEF 14A", "PRE 14C", "DEF 14C"):
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

    def test_same_day_proxy_does_not_guess_event_order(self):
        for form in ("PRE 14A", "DEF 14A", "PRE 14C", "DEF 14C"):
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form, "424B4"],
                            "filingDate": ["2026-08-07", "2026-08-07"],
                        }
                    }
                }
                self.assertFalse(
                    followon_sanitizer.has_prior_periodic_report(
                        submissions, "2026-08-07"
                    )
                )

    def test_payload_removes_424b4_when_prior_proxy_proves_public_status(self):
        payload = {
            "filings": [
                {
                    "id": "proxy-followon",
                    "company": "Already Public Proxy Co.",
                    "cik": "1",
                    "form": "424B4",
                    "filed": "2026-06-01",
                    "pricing_date": "2026-06-01",
                }
            ]
        }
        submissions = {
            "filings": {
                "recent": {
                    "form": ["DEF 14A", "424B4"],
                    "filingDate": ["2026-05-14", "2026-06-01"],
                }
            }
        }

        updated, removed = followon_sanitizer.sanitize_payload(
            payload, submissions_loader=lambda cik: submissions
        )

        self.assertEqual([item["id"] for item in removed], ["proxy-followon"])
        self.assertEqual(updated["filings"], [])


if __name__ == "__main__":
    unittest.main()

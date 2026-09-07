import unittest

import followon_sanitizer


class FollowOnRecentRowValidationTests(unittest.TestCase):
    def _payload(self):
        return {
            "filings": [
                {
                    "id": "candidate",
                    "company": "Candidate Co",
                    "cik": "1",
                    "form": "424B4",
                    "filed": "2026-08-07",
                }
            ]
        }

    def test_invalid_recent_filing_date_blocks_release(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["10-Q", "424B4"],
                    "filingDate": ["not-a-date", "2026-08-07"],
                }
            }
        }

        with self.assertRaises(RuntimeError):
            followon_sanitizer.sanitize_payload(
                self._payload(), submissions_loader=lambda cik: submissions
            )

    def test_blank_recent_form_blocks_release(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["", "424B4"],
                    "filingDate": ["2026-05-14", "2026-08-07"],
                }
            }
        }

        with self.assertRaises(RuntimeError):
            followon_sanitizer.sanitize_payload(
                self._payload(), submissions_loader=lambda cik: submissions
            )

    def test_non_string_recent_form_blocks_release(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": [10, "424B4"],
                    "filingDate": ["2026-05-14", "2026-08-07"],
                }
            }
        }

        with self.assertRaises(RuntimeError):
            followon_sanitizer.sanitize_payload(
                self._payload(), submissions_loader=lambda cik: submissions
            )


if __name__ == "__main__":
    unittest.main()

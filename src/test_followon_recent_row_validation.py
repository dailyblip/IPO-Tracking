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

    def test_missing_final_filed_date_does_not_substitute_pricing_date(self):
        payload = {
            "filings": [
                {
                    "id": "candidate",
                    "company": "Candidate Co",
                    "cik": "1",
                    "accession_no": "0000000001-26-000001",
                    "form": "424B4",
                    "filed": "",
                    "pricing_date": "2026-08-07",
                }
            ]
        }
        loader_calls = []

        def loader(cik):
            loader_calls.append(cik)
            raise AssertionError("follow-on sanitizer must defer without an SEC filed date")

        cleaned, removed = followon_sanitizer.sanitize_payload(
            payload, submissions_loader=loader
        )

        self.assertIs(cleaned, payload)
        self.assertEqual(removed, [])
        self.assertEqual(loader_calls, [])


if __name__ == "__main__":
    unittest.main()

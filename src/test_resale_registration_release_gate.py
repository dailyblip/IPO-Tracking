import unittest
from unittest.mock import patch

from resale_registration_sanitizer import _excluded_accessions


class ResaleRegistrationReleaseGateTests(unittest.TestCase):
    def test_s1_sec_evidence_failure_blocks_release(self):
        payload = {
            "filings": [
                {
                    "id": "0001",
                    "accession_no": "0001",
                    "form": "S-1/A",
                    "sec_url": "https://www.sec.gov/Archives/edgar/data/1/0001-index.html",
                }
            ]
        }

        with patch(
            "resale_registration_sanitizer._fetch_filing_text",
            side_effect=RuntimeError("SEC unavailable"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Could not evaluate resale-registration status for 0001",
            ):
                _excluded_accessions(payload)

    def test_non_s1_rows_do_not_require_resale_cover_check(self):
        payload = {
            "filings": [
                {
                    "id": "priced",
                    "accession_no": "0002",
                    "form": "424B4",
                }
            ]
        }

        with patch(
            "resale_registration_sanitizer._fetch_filing_text",
            side_effect=AssertionError("424B4 should not be fetched here"),
        ):
            self.assertEqual(_excluded_accessions(payload), set())


if __name__ == "__main__":
    unittest.main()

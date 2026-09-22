import unittest
from datetime import datetime, timezone

import followon_sanitizer


class CompactSecAcceptanceTests(unittest.TestCase):
    CANDIDATE_ACCESSION = "0000000001-26-000011"

    def _submissions(self, report_time, candidate_time):
        return {
            "filings": {
                "recent": {
                    "form": ["8-K", "424B4"],
                    "filingDate": ["2026-09-01", "2026-09-01"],
                    "accessionNumber": [
                        "0000000001-26-000010",
                        self.CANDIDATE_ACCESSION,
                    ],
                    "acceptanceDateTime": [report_time, candidate_time],
                }
            }
        }

    def test_compact_edgar_time_is_interpreted_as_eastern(self):
        parsed = followon_sanitizer._iso_datetime("20260901130000")
        self.assertEqual(
            parsed,
            datetime(2026, 9, 1, 17, 0, 0, tzinfo=timezone.utc),
        )

    def test_compact_prior_reporting_filing_disqualifies_later_424b4(self):
        submissions = self._submissions("20260901130000", "20260901140000")
        self.assertTrue(
            followon_sanitizer.has_prior_periodic_report(
                submissions,
                "2026-09-01",
                candidate_accession=self.CANDIDATE_ACCESSION,
            )
        )

    def test_compact_reporting_filing_after_candidate_does_not_disqualify(self):
        submissions = self._submissions("20260901150000", "20260901140000")
        self.assertFalse(
            followon_sanitizer.has_prior_periodic_report(
                submissions,
                "2026-09-01",
                candidate_accession=self.CANDIDATE_ACCESSION,
            )
        )

    def test_invalid_compact_acceptance_timestamp_still_blocks_release(self):
        submissions = self._submissions("20261301130000", "20260901140000")
        with self.assertRaises(RuntimeError):
            followon_sanitizer.has_prior_periodic_report(
                submissions,
                "2026-09-01",
                candidate_accession=self.CANDIDATE_ACCESSION,
            )


if __name__ == "__main__":
    unittest.main()

import unittest

import followon_sanitizer


class SameDayFollowOnAcceptanceTests(unittest.TestCase):
    def _submissions(self, report_time, candidate_time):
        return {
            "filings": {
                "recent": {
                    "form": ["8-K", "424B4"],
                    "filingDate": ["2026-09-01", "2026-09-01"],
                    "accessionNumber": [
                        "0000000001-26-000010",
                        "0000000001-26-000011",
                    ],
                    "acceptanceDateTime": [report_time, candidate_time],
                }
            }
        }

    def test_same_day_prior_reporting_filing_disqualifies_later_424b4(self):
        submissions = self._submissions(
            "2026-09-01T13:00:00.000Z",
            "2026-09-01T14:00:00.000Z",
        )
        self.assertTrue(
            followon_sanitizer.has_prior_periodic_report(
                submissions,
                "2026-09-01",
                candidate_accession="0000000001-26-000011",
            )
        )

    def test_same_day_reporting_filing_after_candidate_does_not_disqualify(self):
        submissions = self._submissions(
            "2026-09-01T15:00:00.000Z",
            "2026-09-01T14:00:00.000Z",
        )
        self.assertFalse(
            followon_sanitizer.has_prior_periodic_report(
                submissions,
                "2026-09-01",
                candidate_accession="0000000001-26-000011",
            )
        )

    def test_same_day_without_authoritative_acceptance_order_stays_unresolved(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["8-K", "424B4"],
                    "filingDate": ["2026-09-01", "2026-09-01"],
                    "accessionNumber": [
                        "0000000001-26-000010",
                        "0000000001-26-000011",
                    ],
                }
            }
        }
        self.assertFalse(
            followon_sanitizer.has_prior_periodic_report(
                submissions,
                "2026-09-01",
                candidate_accession="0000000001-26-000011",
            )
        )

    def test_malformed_acceptance_array_blocks_release(self):
        submissions = self._submissions(
            "2026-09-01T13:00:00.000Z",
            "2026-09-01T14:00:00.000Z",
        )
        submissions["filings"]["recent"]["acceptanceDateTime"] = "not-an-array"

        with self.assertRaises(RuntimeError):
            followon_sanitizer.has_prior_periodic_report(
                submissions,
                "2026-09-01",
                candidate_accession="0000000001-26-000011",
            )

    def test_misaligned_acceptance_array_blocks_release(self):
        submissions = self._submissions(
            "2026-09-01T13:00:00.000Z",
            "2026-09-01T14:00:00.000Z",
        )
        submissions["filings"]["recent"]["acceptanceDateTime"] = [
            "2026-09-01T13:00:00.000Z"
        ]

        with self.assertRaises(RuntimeError):
            followon_sanitizer.has_prior_periodic_report(
                submissions,
                "2026-09-01",
                candidate_accession="0000000001-26-000011",
            )

    def test_misaligned_accession_array_blocks_release(self):
        submissions = self._submissions(
            "2026-09-01T13:00:00.000Z",
            "2026-09-01T14:00:00.000Z",
        )
        submissions["filings"]["recent"]["accessionNumber"] = [
            "0000000001-26-000011"
        ]

        with self.assertRaises(RuntimeError):
            followon_sanitizer.has_prior_periodic_report(
                submissions,
                "2026-09-01",
                candidate_accession="0000000001-26-000011",
            )

    def test_invalid_same_day_acceptance_timestamp_blocks_release(self):
        submissions = self._submissions(
            "not-a-timestamp",
            "2026-09-01T14:00:00.000Z",
        )

        with self.assertRaises(RuntimeError):
            followon_sanitizer.has_prior_periodic_report(
                submissions,
                "2026-09-01",
                candidate_accession="0000000001-26-000011",
            )

    def test_invalid_same_day_accession_blocks_release(self):
        submissions = self._submissions(
            "2026-09-01T13:00:00.000Z",
            "2026-09-01T14:00:00.000Z",
        )
        submissions["filings"]["recent"]["accessionNumber"][0] = ""

        with self.assertRaises(RuntimeError):
            followon_sanitizer.has_prior_periodic_report(
                submissions,
                "2026-09-01",
                candidate_accession="0000000001-26-000011",
            )

    def test_pricing_day_does_not_borrow_next_day_424b4_acceptance_order(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["8-K", "424B4"],
                    "filingDate": ["2026-08-31", "2026-09-01"],
                    "accessionNumber": [
                        "0000000001-26-000010",
                        "0000000001-26-000011",
                    ],
                    "acceptanceDateTime": [
                        "2026-08-31T20:00:00.000Z",
                        "2026-09-01T13:00:00.000Z",
                    ],
                }
            }
        }
        self.assertFalse(
            followon_sanitizer.has_prior_periodic_report(
                submissions,
                "2026-08-31",
                candidate_accession="0000000001-26-000011",
            )
        )

    def test_payload_uses_candidate_accession_for_same_day_ordering(self):
        payload = {
            "filings": [
                {
                    "id": "later-offering",
                    "company": "Already Public Co.",
                    "cik": "1",
                    "accession_no": "0000000001-26-000011",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-09-01",
                    "pricing_date": "2026-09-01",
                }
            ]
        }
        submissions = self._submissions(
            "2026-09-01T13:00:00.000Z",
            "2026-09-01T14:00:00.000Z",
        )

        updated, removed = followon_sanitizer.sanitize_payload(
            payload,
            submissions_loader=lambda cik: submissions,
        )

        self.assertEqual([item["id"] for item in removed], ["later-offering"])
        self.assertEqual(updated["filings"], [])

    def test_payload_orders_reporting_against_final_filing_date_not_pricing_date(self):
        payload = {
            "filings": [
                {
                    "id": "next-day-final",
                    "company": "Already Public Co.",
                    "cik": "1",
                    "accession_no": "0000000001-26-000011",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-09-01",
                    "pricing_date": "2026-08-31",
                }
            ]
        }
        submissions = self._submissions(
            "2026-09-01T13:00:00.000Z",
            "2026-09-01T14:00:00.000Z",
        )

        updated, removed = followon_sanitizer.sanitize_payload(
            payload,
            submissions_loader=lambda cik: submissions,
        )

        self.assertEqual([item["id"] for item in removed], ["next-day-final"])
        self.assertEqual(updated["filings"], [])


if __name__ == "__main__":
    unittest.main()

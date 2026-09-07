import unittest

import followon_sanitizer


class FollowOnCandidateIdentityTests(unittest.TestCase):
    ACCESSION = "0000000001-26-000001"

    def _payload(self, accession=ACCESSION):
        filing = {
            "id": "candidate",
            "company": "Candidate Co",
            "cik": "1",
            "form": "424B4",
            "filed": "2026-08-07",
        }
        if accession is not None:
            filing["accession_no"] = accession
        return {"filings": [filing]}

    def _submissions(self, forms=None, dates=None, accessions=None):
        recent = {
            "form": forms if forms is not None else ["424B4"],
            "filingDate": dates if dates is not None else ["2026-08-07"],
        }
        if accessions is not None:
            recent["accessionNumber"] = accessions
        return {"filings": {"recent": recent}}

    def _sanitize(self, payload, submissions):
        return followon_sanitizer.sanitize_payload(
            payload, submissions_loader=lambda cik: submissions
        )

    def test_valid_supplied_accession_binds_to_candidate_424b4(self):
        payload = self._payload()
        submissions = self._submissions(accessions=[self.ACCESSION])

        updated, removed = self._sanitize(payload, submissions)

        self.assertIs(updated, payload)
        self.assertEqual(removed, [])

    def test_supplied_accession_missing_from_sec_history_blocks_release(self):
        payload = self._payload()
        submissions = self._submissions(accessions=["0000000001-26-000002"])

        with self.assertRaises(RuntimeError):
            self._sanitize(payload, submissions)

    def test_duplicate_supplied_accession_match_blocks_release(self):
        payload = self._payload()
        submissions = self._submissions(
            forms=["424B4", "424B4"],
            dates=["2026-08-07", "2026-08-07"],
            accessions=[self.ACCESSION, self.ACCESSION],
        )

        with self.assertRaises(RuntimeError):
            self._sanitize(payload, submissions)

    def test_supplied_accession_resolving_to_non_424b4_blocks_release(self):
        payload = self._payload()
        submissions = self._submissions(
            forms=["S-1/A"],
            accessions=[self.ACCESSION],
        )

        with self.assertRaises(RuntimeError):
            self._sanitize(payload, submissions)

    def test_supplied_accession_with_different_filing_date_blocks_release(self):
        payload = self._payload()
        submissions = self._submissions(
            dates=["2026-08-06"],
            accessions=[self.ACCESSION],
        )

        with self.assertRaises(RuntimeError):
            self._sanitize(payload, submissions)

    def test_malformed_supplied_accession_blocks_release(self):
        payload = self._payload(accession="1-26-1")
        submissions = self._submissions(accessions=[self.ACCESSION])

        with self.assertRaises(RuntimeError):
            self._sanitize(payload, submissions)

    def test_missing_public_accession_remains_owned_by_final_release_gate(self):
        payload = self._payload(accession=None)
        submissions = self._submissions()

        updated, removed = self._sanitize(payload, submissions)

        self.assertIs(updated, payload)
        self.assertEqual(removed, [])

    def test_unrelated_malformed_sec_accession_does_not_block_valid_match(self):
        payload = self._payload()
        submissions = self._submissions(
            forms=["S-1/A", "424B4"],
            dates=["2026-08-01", "2026-08-07"],
            accessions=["malformed-unrelated", self.ACCESSION],
        )

        updated, removed = self._sanitize(payload, submissions)

        self.assertIs(updated, payload)
        self.assertEqual(removed, [])


if __name__ == "__main__":
    unittest.main()

import unittest

import ticker_listing_reconciler as reconciler


class MissingTickerLineageRecoveryTests(unittest.TestCase):
    def _public_amendment(self):
        return {
            "id": "0001628280-26-060761",
            "accession_no": "0001628280-26-060761",
            "company": "SB Energy, Inc.",
            "cik": "0002133037",
            "ticker": "",
            "form": "S-1/A",
            "filed": "2026-09-04",
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/2133037/"
                "000162828026060761/0001628280-26-060761-index.htm"
            ),
            reconciler._REGISTRATION_FILE_NUMBER_KEY: "333-298675",
        }

    def _submission_rows(self):
        return {
            "0002133037": [
                {
                    "accession_no": "0001628280-26-060761",
                    "form": "S-1/A",
                    "file_number": "333-298675",
                    "filing_date": "2026-09-04",
                },
                {
                    "accession_no": "0001628280-26-059639",
                    "form": "S-1",
                    "file_number": "333-298675",
                    "filing_date": "2026-08-31",
                },
            ]
        }

    def test_compact_watch_recovers_ticker_from_omitted_prior_s1(self):
        amendment = self._public_amendment()
        payload = {"filings": [amendment]}
        registration_map = {
            ("0002133037", "0001628280-26-060761"): "333-298675"
        }
        lineage_records = reconciler._missing_registration_lineage_records(
            [amendment],
            registration_map,
            self._submission_rows(),
        )

        self.assertEqual(len(lineage_records), 1)
        self.assertEqual(
            lineage_records[0]["accession_no"],
            "0001628280-26-059639",
        )
        self.assertEqual(
            lineage_records[0]["sec_url"],
            (
                "https://www.sec.gov/Archives/edgar/data/2133037/"
                "000162828026059639/0001628280-26-059639-index.htm"
            ),
        )

        texts = {
            "0001628280-26-060761": (
                "This exhibits-only amendment does not repeat listing terms."
            ),
            "0001628280-26-059639": (
                "Prior to this offering, there has been no public market for our "
                "common stock. We have applied to list our common stock on The "
                "Nasdaq Global Select Market under the symbol “SBE.”"
            ),
        }
        updated, conflicts = reconciler.reconcile_payload(
            payload,
            fetch_text=lambda record: texts[record["accession_no"]],
            lineage_records=lineage_records,
        )

        self.assertEqual((updated, conflicts), (1, 0))
        self.assertEqual(amendment["ticker"], "SBE")

    def test_different_registration_cannot_seed_ticker(self):
        amendment = self._public_amendment()
        rows = self._submission_rows()
        rows["0002133037"][1]["file_number"] = "333-OLD"
        registration_map = {
            ("0002133037", "0001628280-26-060761"): "333-298675"
        }

        lineage_records = reconciler._missing_registration_lineage_records(
            [amendment],
            registration_map,
            rows,
        )

        self.assertEqual(lineage_records, [])

    def test_same_day_omitted_lineage_does_not_infer_order(self):
        amendment = self._public_amendment()
        rows = self._submission_rows()
        rows["0002133037"][1]["filing_date"] = "2026-09-04"
        registration_map = {
            ("0002133037", "0001628280-26-060761"): "333-298675"
        }
        lineage_records = reconciler._missing_registration_lineage_records(
            [amendment],
            registration_map,
            rows,
        )
        texts = {
            "0001628280-26-060761": "No listing symbol is repeated here.",
            "0001628280-26-059639": (
                "We have applied to list our common stock on Nasdaq under the "
                "symbol SBE."
            ),
        }

        updated, conflicts = reconciler.reconcile_payload(
            {"filings": [amendment]},
            fetch_text=lambda record: texts[record["accession_no"]],
            lineage_records=lineage_records,
        )

        self.assertEqual((updated, conflicts), (0, 0))
        self.assertEqual(amendment["ticker"], "")


if __name__ == "__main__":
    unittest.main()

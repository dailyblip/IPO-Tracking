import unittest

import ticker_listing_reconciler as reconciler


class TickerSameDayLineageGuardTests(unittest.TestCase):
    def test_same_day_sibling_blocks_older_ticker_carry_forward_without_acceptance_time(self):
        payload = {
            "filings": [
                {
                    "id": "current",
                    "cik": "0002133037",
                    "ticker": "OLD",
                    "form": "S-1/A",
                    "filed": "2026-09-04",
                    "sec_url": "https://www.sec.gov/current-index.htm",
                },
                {
                    "id": "same-day",
                    "cik": "0002133037",
                    "ticker": "",
                    "form": "S-1/A",
                    "filed": "2026-09-04",
                    "sec_url": "https://www.sec.gov/same-day-index.htm",
                },
                {
                    "id": "earlier",
                    "cik": "0002133037",
                    "ticker": "",
                    "form": "S-1",
                    "filed": "2026-09-01",
                    "sec_url": "https://www.sec.gov/earlier-index.htm",
                },
            ]
        }
        texts = {
            "current": "This amendment does not repeat listing terms.",
            "same-day": (
                "We have applied to list our common stock on Nasdaq under the symbol NEW."
            ),
            "earlier": (
                "We have applied to list our common stock on Nasdaq under the symbol OLD."
            ),
        }

        updated, conflicts = reconciler.reconcile_payload(
            payload, fetch_text=lambda record: texts[record["id"]]
        )

        self.assertEqual(conflicts, 0)
        self.assertEqual(updated, 3)
        self.assertEqual(payload["filings"][0]["ticker"], "")
        self.assertEqual(payload["filings"][1]["ticker"], "NEW")
        self.assertEqual(payload["filings"][2]["ticker"], "OLD")

    def test_same_day_prior_acceptance_can_carry_unambiguous_ticker_forward(self):
        acceptance_key = reconciler._REGISTRATION_ACCEPTANCE_DATETIME_KEY
        payload = {
            "filings": [
                {
                    "id": "current",
                    "cik": "0002133037",
                    "ticker": "",
                    "form": "S-1/A",
                    "filed": "2026-09-04",
                    "sec_url": "https://www.sec.gov/current-index.htm",
                    acceptance_key: "20260904113000",
                },
                {
                    "id": "same-day-prior",
                    "cik": "0002133037",
                    "ticker": "",
                    "form": "S-1/A",
                    "filed": "2026-09-04",
                    "sec_url": "https://www.sec.gov/same-day-prior-index.htm",
                    acceptance_key: "20260904101500",
                },
                {
                    "id": "earlier",
                    "cik": "0002133037",
                    "ticker": "",
                    "form": "S-1",
                    "filed": "2026-09-01",
                    "sec_url": "https://www.sec.gov/earlier-index.htm",
                    acceptance_key: "20260901100000",
                },
            ]
        }
        texts = {
            "current": "This amendment does not repeat listing terms.",
            "same-day-prior": (
                "We have applied to list our common stock on Nasdaq under the symbol OLD."
            ),
            "earlier": (
                "We have applied to list our common stock on Nasdaq under the symbol OLD."
            ),
        }

        _updated, conflicts = reconciler.reconcile_payload(
            payload, fetch_text=lambda record: texts[record["id"]]
        )

        self.assertEqual(conflicts, 0)
        self.assertEqual(payload["filings"][0]["ticker"], "OLD")

    def test_same_day_later_acceptance_does_not_block_older_lineage(self):
        acceptance_key = reconciler._REGISTRATION_ACCEPTANCE_DATETIME_KEY
        payload = {
            "filings": [
                {
                    "id": "current",
                    "cik": "0002133037",
                    "ticker": "",
                    "form": "S-1/A",
                    "filed": "2026-09-04",
                    "sec_url": "https://www.sec.gov/current-index.htm",
                    acceptance_key: "20260904101500",
                },
                {
                    "id": "same-day-later",
                    "cik": "0002133037",
                    "ticker": "",
                    "form": "S-1/A",
                    "filed": "2026-09-04",
                    "sec_url": "https://www.sec.gov/same-day-later-index.htm",
                    acceptance_key: "20260904113000",
                },
                {
                    "id": "earlier",
                    "cik": "0002133037",
                    "ticker": "",
                    "form": "S-1",
                    "filed": "2026-09-01",
                    "sec_url": "https://www.sec.gov/earlier-index.htm",
                    acceptance_key: "20260901100000",
                },
            ]
        }
        texts = {
            "current": "This amendment does not repeat listing terms.",
            "same-day-later": (
                "We have applied to list our common stock on Nasdaq under the symbol NEW."
            ),
            "earlier": (
                "We have applied to list our common stock on Nasdaq under the symbol OLD."
            ),
        }

        _updated, conflicts = reconciler.reconcile_payload(
            payload, fetch_text=lambda record: texts[record["id"]]
        )

        self.assertEqual(conflicts, 0)
        self.assertEqual(payload["filings"][0]["ticker"], "OLD")
        self.assertEqual(payload["filings"][1]["ticker"], "NEW")

    def test_equal_same_day_acceptance_fails_closed(self):
        acceptance_key = reconciler._REGISTRATION_ACCEPTANCE_DATETIME_KEY
        payload = {
            "filings": [
                {
                    "id": "current",
                    "cik": "0002133037",
                    "ticker": "OLD",
                    "form": "S-1/A",
                    "filed": "2026-09-04",
                    "sec_url": "https://www.sec.gov/current-index.htm",
                    acceptance_key: "20260904101500",
                },
                {
                    "id": "same-day",
                    "cik": "0002133037",
                    "ticker": "",
                    "form": "S-1/A",
                    "filed": "2026-09-04",
                    "sec_url": "https://www.sec.gov/same-day-index.htm",
                    acceptance_key: "20260904101500",
                },
            ]
        }
        texts = {
            "current": "This amendment does not repeat listing terms.",
            "same-day": (
                "We have applied to list our common stock on Nasdaq under the symbol OLD."
            ),
        }

        reconciler.reconcile_payload(
            payload, fetch_text=lambda record: texts[record["id"]]
        )

        self.assertEqual(payload["filings"][0]["ticker"], "")

    def test_malformed_same_day_acceptance_fails_closed(self):
        acceptance_key = reconciler._REGISTRATION_ACCEPTANCE_DATETIME_KEY
        payload = {
            "filings": [
                {
                    "id": "current",
                    "cik": "0002133037",
                    "ticker": "OLD",
                    "form": "S-1/A",
                    "filed": "2026-09-04",
                    "sec_url": "https://www.sec.gov/current-index.htm",
                    acceptance_key: "20260904101500",
                },
                {
                    "id": "same-day",
                    "cik": "0002133037",
                    "ticker": "",
                    "form": "S-1/A",
                    "filed": "2026-09-04",
                    "sec_url": "https://www.sec.gov/same-day-index.htm",
                    acceptance_key: "not-a-time",
                },
            ]
        }
        texts = {
            "current": "This amendment does not repeat listing terms.",
            "same-day": (
                "We have applied to list our common stock on Nasdaq under the symbol OLD."
            ),
        }

        reconciler.reconcile_payload(
            payload, fetch_text=lambda record: texts[record["id"]]
        )

        self.assertEqual(payload["filings"][0]["ticker"], "")


if __name__ == "__main__":
    unittest.main()

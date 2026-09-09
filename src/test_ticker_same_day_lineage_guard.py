import unittest

import ticker_listing_reconciler as reconciler


class TickerSameDayLineageGuardTests(unittest.TestCase):
    def test_same_day_sibling_blocks_older_ticker_carry_forward(self):
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


if __name__ == "__main__":
    unittest.main()

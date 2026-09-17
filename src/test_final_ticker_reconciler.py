import unittest
from bs4 import BeautifulSoup

import final_ticker_reconciler


class FinalTickerReconcilerTests(unittest.TestCase):
    def _payload(self):
        return {
            "generated_at": "2026-09-17T00:00:00+00:00",
            "filings": [
                {
                    "id": "0001193125-26-326453",
                    "accession_no": "0001193125-26-326453",
                    "cik": "0002127043",
                    "company": "Jersey Mike's Subs Inc.",
                    "ticker": "",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-07-31",
                    "pricing_date": "2026-07-30",
                    "offering_price": 23.0,
                }
            ],
        }

    @staticmethod
    def _jersey_soup():
        return BeautifulSoup(
            """
            <html><body>
            <p>This is our initial public offering of shares of Class A common stock.</p>
            <p>Our Class A common stock has been approved for listing on the New York
            Stock Exchange under the trading symbol “JMKE”.</p>
            <p>The initial public offering price is $23.00 per share.</p>
            </body></html>
            """,
            "lxml",
        )

    def test_transient_final_fetch_retries_and_recovers_sec_confirmed_ticker(self):
        payload = self._payload()
        calls = []

        def loader(record):
            calls.append(record["accession_no"])
            if len(calls) == 1:
                raise RuntimeError("temporary SEC transport error")
            return self._jersey_soup()

        payload, recovered = final_ticker_reconciler.recover_payload(
            payload,
            soup_loader=loader,
            attempts=2,
            retry_delay_seconds=0,
        )

        self.assertEqual(recovered, 1)
        self.assertEqual(calls, ["0001193125-26-326453"] * 2)
        filing = payload["filings"][0]
        self.assertEqual(filing["ticker"], "JMKE")
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)

    def test_final_cover_silent_about_ticker_remains_blank(self):
        payload = self._payload()
        silent = BeautifulSoup(
            "<html><body><p>The initial public offering price is $23.00 per share.</p></body></html>",
            "lxml",
        )

        payload, recovered = final_ticker_reconciler.recover_payload(
            payload,
            soup_loader=lambda record: silent,
            attempts=1,
            retry_delay_seconds=0,
        )

        self.assertEqual(recovered, 0)
        self.assertEqual(payload["filings"][0]["ticker"], "")

    def test_exhausted_final_fetch_failure_remains_blank(self):
        payload = self._payload()
        calls = []

        def loader(record):
            calls.append(record["accession_no"])
            raise RuntimeError("SEC unavailable")

        payload, recovered = final_ticker_reconciler.recover_payload(
            payload,
            soup_loader=loader,
            attempts=3,
            retry_delay_seconds=0,
        )

        self.assertEqual(recovered, 0)
        self.assertEqual(len(calls), 3)
        self.assertEqual(payload["filings"][0]["ticker"], "")

    def test_conflicting_accession_identity_is_not_recovered(self):
        payload = self._payload()
        payload["filings"][0]["id"] = "0001193125-26-999999"
        calls = []

        payload, recovered = final_ticker_reconciler.recover_payload(
            payload,
            soup_loader=lambda record: calls.append(record) or self._jersey_soup(),
            attempts=2,
            retry_delay_seconds=0,
        )

        self.assertEqual(recovered, 0)
        self.assertEqual(calls, [])
        self.assertEqual(payload["filings"][0]["ticker"], "")

    def test_prepricing_row_is_never_promoted_by_ticker_recovery(self):
        payload = self._payload()
        filing = payload["filings"][0]
        filing["form"] = "S-1/A"
        filing["stage"] = "Pre-pricing"
        calls = []

        payload, recovered = final_ticker_reconciler.recover_payload(
            payload,
            soup_loader=lambda record: calls.append(record) or self._jersey_soup(),
            attempts=2,
            retry_delay_seconds=0,
        )

        self.assertEqual(recovered, 0)
        self.assertEqual(calls, [])
        self.assertEqual(payload["filings"][0]["ticker"], "")


if __name__ == "__main__":
    unittest.main()

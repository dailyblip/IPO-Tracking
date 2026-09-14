import unittest

import ticker_listing_reconciler as reconciler


class AlopexxTickerRegressionTests(unittest.TestCase):
    def test_applied_to_have_common_stock_listed_is_current_ticker_evidence(self):
        text = (
            'We have applied to have our common stock listed on the NYSE American LLC '
            '(the “NYSE American”) under the symbol “ALPX”.'
        )

        self.assertEqual(reconciler.extract_current_listing_tickers(text), {"ALPX"})

    def test_reconcile_populates_blank_ticker_from_applied_to_have_listing(self):
        payload = {
            "filings": [
                {
                    "id": "alopexx",
                    "company": "Alopexx, Inc.",
                    "ticker": "",
                    "form": "S-1/A",
                    "sec_url": "https://www.sec.gov/example-index.htm",
                }
            ]
        }
        text = (
            "We have applied to have our common stock listed on the NYSE American LLC "
            "under the symbol ‘ALPX’."
        )

        updated, conflicts = reconciler.reconcile_payload(
            payload, fetch_text=lambda record: text
        )

        self.assertEqual((updated, conflicts), (1, 0))
        self.assertEqual(payload["filings"][0]["ticker"], "ALPX")


if __name__ == "__main__":
    unittest.main()

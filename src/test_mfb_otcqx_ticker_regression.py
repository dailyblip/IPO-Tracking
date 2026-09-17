import unittest

import ticker_listing_reconciler as reconciler


class MfbOtcqxTickerRegressionTests(unittest.TestCase):
    def test_expected_future_otcqx_quote_is_current_listing_evidence(self):
        text = (
            "Mutual Federal Bancorp, Inc. historically traded in the over-the-counter market. "
            "Following the conversion, we expect that our common stock will be quoted on "
            "the OTCQX Market under the symbol ‘MFDB’."
        )
        self.assertEqual(reconciler.extract_current_listing_tickers(text), {"MFDB"})

    def test_predecessor_current_quote_does_not_seed_new_issuer_ticker(self):
        text = (
            "Mutual Federal Bancorp, Inc. is currently quoted on the OTCQX Market under "
            "the symbol MFDB. This prospectus relates to the conversion and stock offering."
        )
        self.assertEqual(reconciler.extract_current_listing_tickers(text), set())


if __name__ == "__main__":
    unittest.main()

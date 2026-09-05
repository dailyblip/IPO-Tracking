import unittest

import ticker_listing_reconciler as reconciler


class TickerListingReconcilerTests(unittest.TestCase):
    def test_current_ipo_listing_outranks_historical_symbol_context(self):
        text = (
            "The predecessor's common stock was previously listed on the NYSE under "
            "the symbol MW. We have applied to list our common stock on the Nasdaq "
            "Global Select Market (Nasdaq) under the symbol ‘MENW’."
        )
        self.assertEqual(
            reconciler.extract_current_listing_tickers(text),
            {"MENW"},
        )

    def test_reconcile_replaces_stale_existing_ticker(self):
        payload = {
            "filings": [
                {
                    "id": "example",
                    "company": "Example Co",
                    "ticker": "OLD",
                    "form": "S-1/A",
                    "sec_url": "https://www.sec.gov/example-index.htm",
                }
            ]
        }
        text = (
            "We have applied to list our common stock on Nasdaq under the symbol "
            "‘NEW’."
        )
        updated, conflicts = reconciler.reconcile_payload(
            payload, fetch_text=lambda record: text
        )
        self.assertEqual((updated, conflicts), (1, 0))
        self.assertEqual(payload["filings"][0]["ticker"], "NEW")

    def test_current_amendment_can_replace_earlier_proposed_ticker(self):
        """A later S-1/A listing statement controls over a stale earlier S-1 symbol."""
        payload = {
            "filings": [
                {
                    "id": "amended-ipo",
                    "company": "Example Returning Issuer",
                    "ticker": "MENW",
                    "form": "S-1/A",
                    "sec_url": "https://www.sec.gov/example-amendment-index.htm",
                }
            ]
        }
        current_amendment_text = (
            "Prior to this offering, there has been no public market for our common stock. "
            "We have applied to list our common stock on the Nasdaq Global Select Market "
            "(Nasdaq) under the symbol ‘MW’."
        )
        updated, conflicts = reconciler.reconcile_payload(
            payload, fetch_text=lambda record: current_amendment_text
        )
        self.assertEqual((updated, conflicts), (1, 0))
        self.assertEqual(payload["filings"][0]["ticker"], "MW")

    def test_conflicting_current_listing_symbols_fail_closed(self):
        payload = {
            "filings": [
                {
                    "id": "example",
                    "company": "Example Co",
                    "ticker": "OLD",
                    "form": "S-1",
                    "sec_url": "https://www.sec.gov/example-index.htm",
                }
            ]
        }
        text = (
            "We have applied to list our common stock on Nasdaq under the symbol AAA. "
            "We have applied to list our common stock on NYSE under the symbol BBB."
        )
        updated, conflicts = reconciler.reconcile_payload(
            payload, fetch_text=lambda record: text
        )
        self.assertEqual((updated, conflicts), (1, 1))
        self.assertEqual(payload["filings"][0]["ticker"], "")

    def test_no_current_listing_statement_preserves_existing_ticker(self):
        payload = {
            "filings": [
                {
                    "id": "example",
                    "ticker": "KEEP",
                    "form": "S-1",
                    "sec_url": "https://www.sec.gov/example-index.htm",
                }
            ]
        }
        updated, conflicts = reconciler.reconcile_payload(
            payload,
            fetch_text=lambda record: "Historical trading symbol OLD was discussed.",
        )
        self.assertEqual((updated, conflicts), (0, 0))
        self.assertEqual(payload["filings"][0]["ticker"], "KEEP")


if __name__ == "__main__":
    unittest.main()

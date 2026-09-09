import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

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

    def test_current_listing_symbol_supports_exchange_punctuation_without_truncation(self):
        cases = (
            (
                "We have applied to list our common stock on Nasdaq under the symbol ‘AB.C’.",
                {"AB.C"},
            ),
            (
                "We expect to trade on NYSE under the ticker symbol NEW-A.",
                {"NEW-A"},
            ),
            (
                "We plan to list on Nasdaq under the symbol NEW.",
                {"NEW"},
            ),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(reconciler.extract_current_listing_tickers(text), expected)

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

    def test_no_current_listing_statement_clears_unverified_existing_ticker(self):
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
        self.assertEqual((updated, conflicts), (1, 0))
        self.assertEqual(payload["filings"][0]["ticker"], "")

    def test_no_current_listing_statement_leaves_blank_ticker_unchanged(self):
        payload = {
            "filings": [
                {
                    "id": "example",
                    "ticker": "",
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
        self.assertEqual(payload["filings"][0]["ticker"], "")

    def test_filing_fetch_failure_clears_unverified_existing_ticker(self):
        payload = {
            "filings": [
                {
                    "id": "returning-issuer",
                    "company": "Example Returning Issuer",
                    "ticker": "OLD",
                    "form": "S-1/A",
                    "sec_url": "https://www.sec.gov/example-index.htm",
                }
            ]
        }

        def fail_fetch(_record):
            raise RuntimeError("SEC filing unavailable")

        updated, conflicts = reconciler.reconcile_payload(
            payload, fetch_text=fail_fetch
        )
        self.assertEqual((updated, conflicts), (1, 0))
        self.assertEqual(payload["filings"][0]["ticker"], "")

    def test_filing_fetch_failure_leaves_blank_ticker_unchanged(self):
        payload = {
            "filings": [
                {
                    "id": "new-issuer",
                    "ticker": "",
                    "form": "S-1",
                    "sec_url": "https://www.sec.gov/example-index.htm",
                }
            ]
        }

        def fail_fetch(_record):
            raise RuntimeError("SEC filing unavailable")

        updated, conflicts = reconciler.reconcile_payload(
            payload, fetch_text=fail_fetch
        )
        self.assertEqual((updated, conflicts), (0, 0))
        self.assertEqual(payload["filings"][0]["ticker"], "")

    def test_watch_cli_reconciles_research_queue_and_requests_csv_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            watch = Path(tmp) / "s1_watch.json"
            queue = Path(tmp) / "filings.json"
            watch.write_text('{"filings": []}', encoding="utf-8")
            queue.write_text('{"filings": []}', encoding="utf-8")

            with patch.object(
                reconciler, "reconcile_file", return_value=(0, 0)
            ) as reconcile_file:
                reconciler.main([str(watch)])

            self.assertEqual(
                reconcile_file.call_args_list,
                [call(watch), call(queue, sync_csv=True)],
            )

    def test_queue_reconciliation_keeps_companion_csv_in_sync(self):
        payload = {
            "filings": [
                {
                    "id": "example",
                    "company": "Example Returning Issuer",
                    "ticker": "OLD",
                    "form": "S-1/A",
                    "sec_url": "https://www.sec.gov/example-index.htm",
                }
            ]
        }

        def repair_ticker(candidate):
            candidate["filings"][0]["ticker"] = "NEW"
            return 1, 0

        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "filings.json"
            queue.write_text(json.dumps(payload), encoding="utf-8")

            with patch.object(
                reconciler, "reconcile_payload", side_effect=repair_ticker
            ), patch.object(
                reconciler.dashboard_export, "write_dashboard_csv"
            ) as write_csv:
                updated, conflicts = reconciler.reconcile_file(queue, sync_csv=True)

            self.assertEqual((updated, conflicts), (1, 0))
            rewritten = json.loads(queue.read_text(encoding="utf-8"))
            self.assertEqual(rewritten["filings"][0]["ticker"], "NEW")
            write_csv.assert_called_once_with(rewritten["filings"], queue)


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import market_quote_release_gate


class MarketQuoteSecCrosscheckTests(unittest.TestCase):
    def _payload(self):
        return {
            "filings": [
                {
                    "company": "Example Technology Holdings Inc.",
                    "ticker": "EXMP",
                    "cik": "0001234567",
                    "form": "424B4",
                    "stage": "Priced",
                    "offering_price": 15.0,
                    "current_price": 18.25,
                    "price_updated": "2026-08-31T10:00:00+00:00",
                }
            ]
        }

    def test_sec_crosscheck_clears_stale_ticker_after_provider_name_match(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "filings.json"
            path.write_text(json.dumps(self._payload()), encoding="utf-8")

            with (
                patch.dict(
                    "os.environ",
                    {"SEC_EDGAR_USER_AGENT": "Research Monitor test@example.com"},
                    clear=False,
                ),
                patch.object(
                    market_quote_release_gate.identity,
                    "sanitize_feed",
                    return_value=(1, 0),
                ),
                patch.object(
                    market_quote_release_gate.identity,
                    "_paced_sec_lookup",
                    return_value=lambda cik: {
                        "cik": 1234567,
                        "name": "Example Technology Holdings Inc.",
                        "tickers": ["OLD"],
                    },
                ),
                patch.object(
                    market_quote_release_gate.dashboard_export,
                    "write_dashboard_csv",
                ) as csv_mock,
            ):
                audited, sanitized = market_quote_release_gate.enforce_release_gate(
                    path,
                    api_key="test-key",
                    time_budget_seconds=None,
                )

            self.assertEqual((audited, sanitized), (0, 1))
            filing = json.loads(path.read_text(encoding="utf-8"))["filings"][0]
            self.assertNotIn("current_price", filing)
            self.assertNotIn("price_updated", filing)
            csv_mock.assert_called_once()

    def test_sec_crosscheck_preserves_quote_when_cik_and_ticker_match(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "filings.json"
            path.write_text(json.dumps(self._payload()), encoding="utf-8")

            with (
                patch.dict(
                    "os.environ",
                    {"SEC_EDGAR_USER_AGENT": "Research Monitor test@example.com"},
                    clear=False,
                ),
                patch.object(
                    market_quote_release_gate.identity,
                    "sanitize_feed",
                    return_value=(1, 0),
                ),
                patch.object(
                    market_quote_release_gate.identity,
                    "_paced_sec_lookup",
                    return_value=lambda cik: {
                        "cik": 1234567,
                        "name": "Renamed Example Corporation",
                        "tickers": ["EXMP"],
                    },
                ),
            ):
                audited, sanitized = market_quote_release_gate.enforce_release_gate(
                    path,
                    api_key="test-key",
                    time_budget_seconds=None,
                )

            self.assertEqual((audited, sanitized), (1, 0))
            filing = json.loads(path.read_text(encoding="utf-8"))["filings"][0]
            self.assertEqual(filing["current_price"], 18.25)

    def test_sec_crosscheck_clears_quote_when_filing_cik_is_missing(self):
        payload = self._payload()
        payload["filings"][0]["cik"] = ""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "filings.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with (
                patch.dict(
                    "os.environ",
                    {"SEC_EDGAR_USER_AGENT": "Research Monitor test@example.com"},
                    clear=False,
                ),
                patch.object(
                    market_quote_release_gate.identity,
                    "sanitize_feed",
                    return_value=(1, 0),
                ),
                patch.object(
                    market_quote_release_gate.dashboard_export,
                    "write_dashboard_csv",
                ) as csv_mock,
            ):
                audited, sanitized = market_quote_release_gate.enforce_release_gate(
                    path,
                    api_key="test-key",
                    time_budget_seconds=None,
                )

            self.assertEqual((audited, sanitized), (0, 1))
            filing = json.loads(path.read_text(encoding="utf-8"))["filings"][0]
            self.assertNotIn("current_price", filing)
            csv_mock.assert_called_once()

    def test_sec_crosscheck_clears_quote_when_sec_cik_does_not_match(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "filings.json"
            path.write_text(json.dumps(self._payload()), encoding="utf-8")

            with (
                patch.dict(
                    "os.environ",
                    {"SEC_EDGAR_USER_AGENT": "Research Monitor test@example.com"},
                    clear=False,
                ),
                patch.object(
                    market_quote_release_gate.identity,
                    "sanitize_feed",
                    return_value=(1, 0),
                ),
                patch.object(
                    market_quote_release_gate.identity,
                    "_paced_sec_lookup",
                    return_value=lambda cik: {
                        "cik": 9999999,
                        "name": "Example Technology Holdings Inc.",
                        "tickers": ["EXMP"],
                    },
                ),
                patch.object(
                    market_quote_release_gate.dashboard_export,
                    "write_dashboard_csv",
                ) as csv_mock,
            ):
                audited, sanitized = market_quote_release_gate.enforce_release_gate(
                    path,
                    api_key="test-key",
                    time_budget_seconds=None,
                )

            self.assertEqual((audited, sanitized), (0, 1))
            filing = json.loads(path.read_text(encoding="utf-8"))["filings"][0]
            self.assertNotIn("current_price", filing)
            csv_mock.assert_called_once()

    def test_sec_crosscheck_clears_quote_when_sec_cik_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "filings.json"
            path.write_text(json.dumps(self._payload()), encoding="utf-8")

            with (
                patch.dict(
                    "os.environ",
                    {"SEC_EDGAR_USER_AGENT": "Research Monitor test@example.com"},
                    clear=False,
                ),
                patch.object(
                    market_quote_release_gate.identity,
                    "sanitize_feed",
                    return_value=(1, 0),
                ),
                patch.object(
                    market_quote_release_gate.identity,
                    "_paced_sec_lookup",
                    return_value=lambda cik: {
                        "name": "Example Technology Holdings Inc.",
                        "tickers": ["EXMP"],
                    },
                ),
                patch.object(
                    market_quote_release_gate.dashboard_export,
                    "write_dashboard_csv",
                ) as csv_mock,
            ):
                audited, sanitized = market_quote_release_gate.enforce_release_gate(
                    path,
                    api_key="test-key",
                    time_budget_seconds=None,
                )

            self.assertEqual((audited, sanitized), (0, 1))
            filing = json.loads(path.read_text(encoding="utf-8"))["filings"][0]
            self.assertNotIn("current_price", filing)
            csv_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()

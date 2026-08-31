import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import market_quote_identity
import market_quote_release_gate


class MarketQuoteReleaseGateTests(unittest.TestCase):
    def _payload(self):
        return {
            "filings": [
                {
                    "company": "Example Priced Inc.",
                    "ticker": "EXMP",
                    "cik": "0001234567",
                    "form": "424B4",
                    "stage": "Priced",
                    "offering_price": 15.0,
                    "current_price": 18.25,
                    "price_updated": "2026-08-31T10:00:00+00:00",
                    "signals": [
                        "Offering priced at $15.00 per share",
                        "Largest named holding currently valued at approximately $18M",
                    ],
                    "people": [
                        {
                            "name": "Example Holder",
                            "shares_after_ipo": 1000,
                            "cash_value": 18250,
                            "liquid_value": 18250,
                            "valuation_as_of": "2026-08-31",
                        }
                    ],
                }
            ]
        }

    def test_provider_transport_failure_clears_unverified_quote_and_derivatives(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "filings.json"
            path.write_text(json.dumps(self._payload()), encoding="utf-8")

            with (
                patch.object(
                    market_quote_release_gate.identity,
                    "sanitize_feed",
                    side_effect=market_quote_identity.QuoteProviderError(
                        "provider returned HTTP 503 after 4 attempts"
                    ),
                ),
                patch.object(
                    market_quote_release_gate.dashboard_export,
                    "write_dashboard_csv",
                ) as csv_mock,
            ):
                audited, cleared = market_quote_release_gate.enforce_release_gate(
                    path, api_key="test-key"
                )

            self.assertEqual((audited, cleared), (0, 1))
            payload = json.loads(path.read_text(encoding="utf-8"))
            filing = payload["filings"][0]
            person = filing["people"][0]
            self.assertNotIn("current_price", filing)
            self.assertNotIn("price_updated", filing)
            self.assertEqual(filing["offering_price"], 15.0)
            self.assertEqual(filing["signals"], ["Offering priced at $15.00 per share"])
            self.assertEqual(person["shares_after_ipo"], 1000)
            for field in ("cash_value", "liquid_value", "locked_value", "valuation_as_of"):
                self.assertNotIn(field, person)
            csv_mock.assert_called_once()

    def test_missing_market_data_key_remains_release_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "filings.json"
            path.write_text(json.dumps(self._payload()), encoding="utf-8")
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(
                    market_quote_identity.QuoteProviderError,
                    "MARKET_DATA_API_KEY is required",
                ):
                    market_quote_release_gate.enforce_release_gate(path)

    def test_deterministic_identity_error_is_not_masked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "filings.json"
            path.write_text(json.dumps(self._payload()), encoding="utf-8")
            with patch.object(
                market_quote_release_gate.identity,
                "sanitize_feed",
                side_effect=market_quote_identity.QuoteIdentityError("bad lifecycle"),
            ):
                with self.assertRaisesRegex(
                    market_quote_identity.QuoteIdentityError, "bad lifecycle"
                ):
                    market_quote_release_gate.enforce_release_gate(
                        path, api_key="test-key"
                    )

    def test_successful_identity_gate_preserves_verified_quote(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "filings.json"
            path.write_text(json.dumps(self._payload()), encoding="utf-8")
            with patch.object(
                market_quote_release_gate.identity,
                "sanitize_feed",
                return_value=(1, 0),
            ):
                self.assertEqual(
                    market_quote_release_gate.enforce_release_gate(
                        path, api_key="test-key"
                    ),
                    (1, 0),
                )
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["filings"][0]["current_price"], 18.25)

    def test_daily_workflow_uses_release_safe_quote_gate(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/daily.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "python market_quote_release_gate.py ../docs/data/filings.json",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()

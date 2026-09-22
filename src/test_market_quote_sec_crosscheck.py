import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import market_quote_release_gate


class MarketQuoteSecCrosscheckTests(unittest.TestCase):
    ACCESSION = "0001234567-26-123456"

    def _payload(self):
        return {
            "generated_at": "2026-09-01T10:05:00+00:00",
            "filings": [
                {
                    "id": self.ACCESSION,
                    "accession_no": self.ACCESSION,
                    "company": "Example Technology Holdings Inc.",
                    "ticker": "EXMP",
                    "cik": "0001234567",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-08-31",
                    "pricing_date": "2026-08-31",
                    "offering_price": 15.0,
                    "current_price": 18.25,
                    "price_updated": "2026-09-01T10:00:00+00:00",
                }
            ]
        }

    def _same_day_payload(self, price_updated):
        payload = self._payload()
        payload["generated_at"] = "2026-08-31T14:30:00+00:00"
        payload["filings"][0]["price_updated"] = price_updated
        payload["filings"][0]["signals"] = [
            "Offering priced at $15.00 per share",
            "Largest named holding currently valued at approximately $18M",
        ]
        payload["filings"][0]["people"] = [
            {
                "name": "Example Holder",
                "cash_value": 18250,
                "valuation_as_of": price_updated,
            }
        ]
        return payload

    def _sec_profile(self, acceptance=None):
        profile = {
            "cik": 1234567,
            "name": "Example Technology Holdings Inc.",
            "tickers": ["EXMP"],
        }
        if acceptance is not None:
            profile["filings"] = {
                "recent": {
                    "accessionNumber": [self.ACCESSION],
                    "form": ["424B4"],
                    "filingDate": ["2026-08-31"],
                    "acceptanceDateTime": [acceptance],
                }
            }
        return profile

    def _run_sec_crosscheck(self, payload, sec_profile):
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
                    "_paced_sec_lookup",
                    return_value=lambda cik: sec_profile,
                ),
                patch.object(
                    market_quote_release_gate.dashboard_export,
                    "write_dashboard_csv",
                ),
            ):
                result = market_quote_release_gate._sec_quote_identity_crosscheck(path)
            return result, json.loads(path.read_text(encoding="utf-8"))

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

    def test_sec_crosscheck_fails_closed_on_malformed_sec_ticker_metadata(self):
        malformed_values = (
            {"EXMP": "wrong container"},
            "EXMP",
            ["EXMP", 123],
            ["EXMP", ""],
        )
        for malformed_tickers in malformed_values:
            with self.subTest(tickers=malformed_tickers), tempfile.TemporaryDirectory() as directory:
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
                        return_value=lambda cik, value=malformed_tickers: {
                            "cik": 1234567,
                            "name": "Example Technology Holdings Inc.",
                            "tickers": value,
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

    def test_same_day_quote_before_final_acceptance_is_cleared(self):
        payload = self._same_day_payload("2026-08-31T13:45:00+00:00")
        result, updated = self._run_sec_crosscheck(
            payload,
            self._sec_profile("2026-08-31T10:00:00-04:00"),
        )

        self.assertEqual(result, (0, 1))
        filing = updated["filings"][0]
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertEqual(filing["offering_price"], 15.0)
        self.assertNotIn("cash_value", filing["people"][0])
        self.assertNotIn("valuation_as_of", filing["people"][0])
        self.assertEqual(filing["signals"], ["Offering priced at $15.00 per share"])

    def test_same_day_quote_after_final_acceptance_is_preserved(self):
        payload = self._same_day_payload("2026-08-31T14:15:00+00:00")
        result, updated = self._run_sec_crosscheck(
            payload,
            self._sec_profile("2026-08-31T10:00:00-04:00"),
        )

        self.assertEqual(result, (1, 0))
        filing = updated["filings"][0]
        self.assertEqual(filing["current_price"], 18.25)
        self.assertEqual(filing["price_updated"], "2026-08-31T14:15:00+00:00")
        self.assertEqual(filing["people"][0]["cash_value"], 18250)

    def test_same_day_quote_equal_to_final_acceptance_is_cleared(self):
        payload = self._same_day_payload("2026-08-31T14:00:00+00:00")
        result, updated = self._run_sec_crosscheck(
            payload,
            self._sec_profile("2026-08-31T10:00:00-04:00"),
        )

        self.assertEqual(result, (0, 1))
        self.assertNotIn("current_price", updated["filings"][0])

    def test_same_day_quote_without_acceptance_metadata_fails_closed(self):
        payload = self._same_day_payload("2026-08-31T14:15:00+00:00")
        result, updated = self._run_sec_crosscheck(
            payload,
            self._sec_profile(),
        )

        self.assertEqual(result, (0, 1))
        self.assertNotIn("current_price", updated["filings"][0])

    def test_next_day_quote_does_not_require_intraday_acceptance_metadata(self):
        result, updated = self._run_sec_crosscheck(
            self._payload(),
            self._sec_profile(),
        )

        self.assertEqual(result, (1, 0))
        self.assertEqual(updated["filings"][0]["current_price"], 18.25)

    def test_compact_edgar_acceptance_time_is_interpreted_on_eastern_calendar(self):
        payload = self._same_day_payload("2026-08-31T14:15:00+00:00")
        result, updated = self._run_sec_crosscheck(
            payload,
            self._sec_profile("20260831100000"),
        )

        self.assertEqual(result, (1, 0))
        self.assertEqual(updated["filings"][0]["current_price"], 18.25)


if __name__ == "__main__":
    unittest.main()

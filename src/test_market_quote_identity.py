import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from market_quote_identity import (
    QuoteIdentityError,
    QuoteProviderError,
    _company_names_match,
    _fetch_profile,
    _validate_profile,
    audit_payload,
    sanitize_payload,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class MarketQuoteIdentityTests(unittest.TestCase):
    def test_company_name_matching_normalizes_legal_suffixes_and_punctuation(self):
        self.assertTrue(_company_names_match("Lyntris Inc.", "LYNTRIS, INC"))
        self.assertTrue(
            _company_names_match(
                "Figure Technology Solutions, Inc.",
                "Figure Technology Solutions Inc",
            )
        )
        self.assertFalse(_company_names_match("Standard Nuclear Inc.", "Nuclear Energy Corp"))

    def test_profile_ticker_must_match_filing_ticker(self):
        with self.assertRaisesRegex(QuoteIdentityError, "does not match SEC/filing ticker"):
            _validate_profile("LYNX", "Lyntris Inc.", {"ticker": "OLD", "name": "Lyntris Inc"})

    def test_profile_company_must_match_sec_issuer(self):
        with self.assertRaisesRegex(QuoteIdentityError, "possibly collided quote"):
            _validate_profile(
                "LYNX",
                "Lyntris Inc.",
                {"ticker": "LYNX", "name": "Legacy Mining Holdings Inc."},
            )

    def test_audit_rejects_quote_before_final_priced_lifecycle(self):
        payload = {
            "filings": [
                {
                    "company": "Example Inc.",
                    "ticker": "EXMP",
                    "form": "S-1/A",
                    "stage": "Pre-pricing",
                    "current_price": 12.34,
                }
            ]
        }
        with self.assertRaisesRegex(QuoteIdentityError, "before a final 424B4/Priced"):
            audit_payload(payload, lookup_profile=lambda ticker: {})

    def test_audit_accepts_verified_priced_quote_and_caches_profile_by_ticker(self):
        payload = {
            "filings": [
                {
                    "company": "Lyntris Inc.",
                    "ticker": "LYNX",
                    "form": "424B4",
                    "stage": "Priced",
                    "current_price": 13.87,
                },
                {
                    "company": "Lyntris Inc.",
                    "ticker": "LYNX",
                    "form": "424B4",
                    "stage": "Priced",
                    "current_price": 13.87,
                },
            ]
        }
        calls = []

        def lookup(ticker):
            calls.append(ticker)
            return {"ticker": "LYNX", "name": "Lyntris Inc"}

        self.assertEqual(audit_payload(payload, lookup_profile=lookup), 2)
        self.assertEqual(calls, ["LYNX"])

    def test_release_sanitizer_clears_collided_quote_and_derived_market_values(self):
        payload = {
            "filings": [
                {
                    "company": "Lyntris Inc.",
                    "ticker": "LYNX",
                    "form": "424B4",
                    "stage": "Priced",
                    "offering_price": 17.5,
                    "current_price": 13.87,
                    "price_updated": "2026-08-27T19:01:25+00:00",
                    "signals": [
                        "Offering priced at $17.50 per share",
                        "Largest named holding currently valued at approximately $341M",
                    ],
                    "people": [
                        {
                            "name": "Example Holder",
                            "cash_value": 341000000,
                            "valuation_as_of": "2026-08-27",
                            "locked_value": 100000000,
                            "liquid_value": 241000000,
                            "shares_after_ipo": 1000,
                        }
                    ],
                }
            ]
        }

        payload, audited, sanitized = sanitize_payload(
            payload,
            lookup_profile=lambda ticker: {
                "ticker": "LYNX",
                "name": "Legacy Mining Holdings Inc.",
            },
        )

        filing = payload["filings"][0]
        person = filing["people"][0]
        self.assertEqual(audited, 0)
        self.assertEqual(len(sanitized), 1)
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertEqual(filing["offering_price"], 17.5)
        self.assertEqual(filing["signals"], ["Offering priced at $17.50 per share"])
        for field in ("cash_value", "valuation_as_of", "locked_value", "liquid_value"):
            self.assertNotIn(field, person)
        self.assertEqual(person["shares_after_ipo"], 1000)

    def test_release_sanitizer_clears_quote_when_provider_has_no_profile(self):
        payload = {
            "filings": [
                {
                    "company": "Newly Listed Inc.",
                    "ticker": "NEWI",
                    "form": "424B4",
                    "stage": "Priced",
                    "current_price": 10.25,
                    "price_updated": "2026-08-27T19:01:25+00:00",
                }
            ]
        }

        payload, audited, sanitized = sanitize_payload(
            payload,
            lookup_profile=lambda ticker: {},
        )

        self.assertEqual(audited, 0)
        self.assertEqual(len(sanitized), 1)
        self.assertNotIn("current_price", payload["filings"][0])

    def test_release_sanitizer_does_not_mask_provider_transport_failure(self):
        payload = {
            "filings": [
                {
                    "company": "Lyntris Inc.",
                    "ticker": "LYNX",
                    "form": "424B4",
                    "stage": "Priced",
                    "current_price": 13.87,
                }
            ]
        }

        def lookup(_ticker):
            raise QuoteProviderError("HTTP 429 after retries")

        with self.assertRaisesRegex(QuoteProviderError, "HTTP 429"):
            sanitize_payload(payload, lookup_profile=lookup)
        self.assertEqual(payload["filings"][0]["current_price"], 13.87)

    def test_profile_fetch_retries_rate_limit_then_succeeds(self):
        limited = Mock()
        limited.status_code = 429
        limited.headers = {"Retry-After": "2"}

        success = Mock()
        success.status_code = 200
        success.headers = {}
        success.raise_for_status.return_value = None
        success.json.return_value = {"ticker": "LYNX", "name": "Lyntris Inc"}

        with patch(
            "market_quote_identity.requests.get",
            side_effect=[limited, success],
        ) as get_mock, patch("market_quote_identity.time.sleep") as sleep_mock:
            profile = _fetch_profile("LYNX", "test-key")

        self.assertEqual(profile["ticker"], "LYNX")
        self.assertEqual(get_mock.call_count, 2)
        sleep_mock.assert_called_once_with(2.0)

    def test_release_workflows_verify_quote_identity_before_publication(self):
        daily = (REPO_ROOT / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
        ownership = (
            REPO_ROOT / ".github" / "workflows" / "ownership-refresh.yml"
        ).read_text(encoding="utf-8")

        for workflow, terminal_step in (
            (daily, "- name: Publish Research Monitor data"),
            (ownership, "- name: Validate public feed"),
        ):
            with self.subTest(terminal_step=terminal_step):
                identity_step = workflow.index("- name: Verify market quote issuer identity")
                self.assertIn(
                    "python market_quote_identity.py ../docs/data/filings.json",
                    workflow,
                )
                self.assertLess(identity_step, workflow.index(terminal_step))

        self.assertIn("- 'src/market_quote_identity.py'", ownership)
        self.assertIn("- 'src/test_market_quote_identity.py'", ownership)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

from market_quote_identity import (
    QuoteIdentityError,
    _company_names_match,
    _validate_profile,
    audit_payload,
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

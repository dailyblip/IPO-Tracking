import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ownership-refresh.yml"


class OwnershipReleaseChainContractTests(unittest.TestCase):
    def test_ownership_replay_preserves_full_release_safety_order(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        ordered_steps = [
            "- name: Refresh qualifying IPO history and Stanford affiliations",
            "- name: Reconcile SEC-backed S-1 ticker metadata after ownership regeneration",
            "- name: Reconcile regenerated S-1 registration history",
            "- name: Reconcile resale-only S-1 registrations after ownership regeneration",
            "- name: Exclude non-substantive S-1 form templates after ownership regeneration",
            "- name: Verify fixed pre-pricing Filing Prices after ownership regeneration",
            "- name: Preserve pre-pricing Filing Price provenance after ownership regeneration",
            "- name: Clear market quotes not refreshed in this run",
            "- name: Verify exact final SEC accession identity",
            "- name: Reconcile final 424B4 lifecycle transitions",
            "- name: Converge parallel 424B4 lifecycle transitions",
            "- name: Reconcile authoritative IPO pricing dates",
            "- name: Sanitize impossible lifecycle dates",
            "- name: Remove unresolved final pricing states",
            "- name: Remove post-reporting follow-on/resale offerings",
            "- name: Check archived SEC reporting history",
            "- name: Recover SEC-confirmed Stanford beneficial-owner affiliations",
            "- name: Normalize issuer display names",
            "- name: Enforce public-feed eligibility policy",
            "- name: Preserve authoritative final offering aggregates",
            "- name: Repair malformed issuer locations",
            "- name: Recover authoritative preliminary filing-price ranges",
            "- name: Remove market quotes from pre-pricing records",
            "- name: Verify market quote issuer identity",
            "- name: Run release-blocking regression suite on regenerated feed",
            "- name: Validate regenerated golden records",
            "- name: Validate public feed",
            "- name: Validate V1 public feed schema",
            "- name: Publish refreshed ownership data",
        ]

        positions = [workflow.index(step) for step in ordered_steps]
        self.assertEqual(positions, sorted(positions))

    def test_ownership_replay_keeps_release_blocking_commands(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        required_commands = [
            "python ticker_listing_reconciler.py",
            "python s1_registration_history_gate.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            "python resale_registration_sanitizer.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            "python s1_substantive_registration_gate.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            "python s1_preliminary_price_gate.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            "python s1_price_range_history.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            "python final_accession_identity_guard.py ../docs/data/filings.json",
            "python lifecycle_reconciler.py ../docs/data/filings.json",
            "python lifecycle_convergence.py ../docs/data/filings.json",
            "python pricing_date_reconciler.py ../docs/data/filings.json",
            "python final_pricing_release_gate.py ../docs/data/filings.json",
            "python followon_sanitizer.py ../docs/data/filings.json",
            "python archived_reporting_history_gate.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            "python public_feed_policy.py ../docs/data/filings.json",
            "python offering_value_reconciler.py ../docs/data/filings.json",
            "python filing_price_history.py ../docs/data/filings.json",
            "python prepricing_quote_sanitizer.py ../docs/data/filings.json",
            "python market_quote_release_gate.py ../docs/data/filings.json",
            "python -m unittest discover -s src -p 'test_*.py' -v",
            "python -m unittest discover -s src -p 'test_golden_records.py' -v",
            "python src/feed_schema_contract.py docs/data/filings.json",
        ]

        for command in required_commands:
            with self.subTest(command=command):
                self.assertIn(command, workflow)

    def test_prepricing_history_helper_changes_trigger_ownership_refresh(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("- 'src/s1_price_range_history.py'", workflow)
        self.assertIn("- 'src/test_s1_price_range_history.py'", workflow)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "stanford-backfill-once.yml"


class StanfordBackfillReleaseSafetyChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_stanford_backfill_matches_current_shared_writer_release_chain(self):
        backfill_step = self.workflow.index("- name: Run Stanford historical backfill")
        ordered_steps = [
            "- name: Reconcile SEC-backed S-1 ticker metadata after Stanford regeneration",
            "- name: Reconcile regenerated S-1 registration history",
            "- name: Reconcile resale-only S-1 registrations after Stanford regeneration",
            "- name: Exclude non-substantive S-1 form templates after Stanford regeneration",
            "- name: Verify fixed pre-pricing Filing Prices after Stanford regeneration",
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
            "- name: Enforce public-feed eligibility policy",
            "- name: Preserve authoritative final offering aggregates",
            "- name: Recover authoritative preliminary filing-price ranges",
            "- name: Remove market quotes from pre-pricing records",
            "- name: Verify market quote issuer identity",
            "- name: Run release-blocking regression suite on generated feed",
            "- name: Validate generated lifecycle uniqueness",
            "- name: Validate V1 public feed schema",
            "- name: Validate refreshed golden records",
            "- name: Publish Research Monitor data",
        ]

        positions = [self.workflow.index(step) for step in ordered_steps]
        self.assertTrue(all(position > backfill_step for position in positions))
        self.assertEqual(positions, sorted(positions))

    def test_stanford_backfill_invokes_required_release_gates(self):
        required_commands = [
            "python ticker_listing_reconciler.py",
            "python s1_registration_history_gate.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            "python resale_registration_sanitizer.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            "python s1_substantive_registration_gate.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            "python s1_preliminary_price_gate.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            "python final_accession_identity_guard.py ../docs/data/filings.json",
            "python lifecycle_convergence.py ../docs/data/filings.json",
            "python archived_reporting_history_gate.py ../docs/data/s1_watch.json ../docs/data/filings.json",
        ]

        for command in required_commands:
            with self.subTest(command=command):
                self.assertIn(command, self.workflow)


if __name__ == "__main__":
    unittest.main()

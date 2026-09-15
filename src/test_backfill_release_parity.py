import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKFILL_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "backfill.yml"


class BackfillReleaseParityTests(unittest.TestCase):
    def test_backfill_rechecks_regenerated_s1_identity_and_classification_before_publish(self):
        workflow = BACKFILL_WORKFLOW.read_text(encoding="utf-8")
        backfill_step = workflow.index("- name: Run backfill")
        ordered_steps = [
            "- name: Reconcile SEC-backed S-1 ticker metadata after backfill regeneration",
            "- name: Reconcile regenerated S-1 registration history after backfill",
            "- name: Reconcile resale-only S-1 registrations after backfill regeneration",
            "- name: Exclude non-substantive S-1 form templates after backfill regeneration",
            "- name: Verify fixed pre-pricing Filing Prices against SEC cover terms",
            "- name: Remove post-reporting follow-on/resale offerings",
            "- name: Check archived SEC reporting history after backfill",
            "- name: Enforce public-feed eligibility policy",
            "- name: Recover authoritative preliminary filing-price ranges",
            "- name: Remove market quotes from pre-pricing records",
            "- name: Verify market quote issuer identity",
            "- name: Run release-blocking regression suite on generated feed",
            "- name: Publish Research Monitor data",
        ]

        positions = [workflow.index(step) for step in ordered_steps]
        self.assertTrue(all(position > backfill_step for position in positions))
        self.assertEqual(positions, sorted(positions))
        self.assertIn("python ticker_listing_reconciler.py", workflow)
        self.assertIn(
            "python s1_registration_history_gate.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            workflow,
        )
        self.assertIn(
            "python resale_registration_sanitizer.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            workflow,
        )
        self.assertIn(
            "python s1_substantive_registration_gate.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            workflow,
        )
        self.assertIn(
            "python s1_preliminary_price_gate.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            workflow,
        )
        self.assertIn(
            "python archived_reporting_history_gate.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            workflow,
        )

    def test_backfill_verifies_preliminary_price_before_lifecycle_promotion(self):
        workflow = BACKFILL_WORKFLOW.read_text(encoding="utf-8")
        preliminary_price_gate = workflow.index(
            "- name: Verify fixed pre-pricing Filing Prices against SEC cover terms"
        )
        lifecycle_reconcile = workflow.index("- name: Reconcile final 424B4 lifecycle transitions")
        final_pricing_gate = workflow.index("- name: Remove unresolved final pricing states")
        publish_step = workflow.index("- name: Publish Research Monitor data")

        self.assertLess(preliminary_price_gate, lifecycle_reconcile)
        self.assertLess(lifecycle_reconcile, final_pricing_gate)
        self.assertLess(final_pricing_gate, publish_step)


if __name__ == "__main__":
    unittest.main()

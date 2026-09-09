import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ownership-refresh.yml"


class OwnershipRefreshS1ContractTests(unittest.TestCase):
    def test_ownership_replay_applies_s1_release_gates_before_publication(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        steps = [
            "- name: Refresh qualifying IPO history and Stanford affiliations",
            "- name: Reconcile regenerated S-1 registration history",
            "- name: Reconcile resale-only S-1 registrations after ownership regeneration",
            "- name: Exclude non-substantive S-1 form templates after ownership regeneration",
            "- name: Verify fixed pre-pricing Filing Prices after ownership regeneration",
            "- name: Clear market quotes not refreshed in this run",
            "- name: Reconcile final 424B4 lifecycle transitions",
            "- name: Validate public feed",
        ]
        positions = [workflow.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))
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

    def test_ownership_refresh_reacts_to_s1_release_gate_changes(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for path in [
            "src/s1_registration_history_gate.py",
            "src/resale_registration_sanitizer.py",
            "src/s1_substantive_registration_gate.py",
            "src/s1_preliminary_price_gate.py",
            "src/test_s1_registration_history_gate.py",
            "src/test_resale_registration_sanitizer.py",
            "src/test_s1_preliminary_price_gate.py",
            "src/test_ownership_refresh_s1_contract.py",
        ]:
            self.assertIn(f"- '{path}'", workflow)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily.yml"
GATE_COMMAND = "python s1_substantive_registration_gate.py ../docs/data/s1_watch.json ../docs/data/filings.json"


class DailyS1SubstantiveGateTests(unittest.TestCase):
    def test_daily_applies_substantive_gate_before_tests_and_after_regeneration(self):
        workflow = DAILY_WORKFLOW.read_text(encoding="utf-8")

        self.assertEqual(workflow.count(GATE_COMMAND), 2)

        pre_gate = workflow.index(
            "- name: Exclude non-substantive S-1 form templates before daily regeneration"
        )
        unit_tests = workflow.index("- name: Run unit tests")
        daily_pipeline = workflow.index("- name: Run daily pipeline")
        regenerated_history = workflow.index("- name: Reconcile regenerated S-1 registration history")
        post_gate = workflow.index(
            "- name: Exclude non-substantive S-1 form templates after daily regeneration"
        )
        release_checks = workflow.index("- name: Verify fixed pre-pricing Filing Prices against SEC cover terms")

        self.assertLess(pre_gate, unit_tests)
        self.assertLess(unit_tests, daily_pipeline)
        self.assertLess(daily_pipeline, regenerated_history)
        self.assertLess(regenerated_history, post_gate)
        self.assertLess(post_gate, release_checks)


if __name__ == "__main__":
    unittest.main()

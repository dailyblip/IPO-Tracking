import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily.yml"


class DailyS1ReleaseSafetyTests(unittest.TestCase):
    def test_daily_reconciles_stale_resale_s1_rows_before_unit_tests(self):
        workflow = DAILY_WORKFLOW.read_text(encoding="utf-8")

        policy = workflow.index("- name: Reconcile checked-in feed with current release policy")
        history = workflow.index("- name: Reconcile resale-only S-1 amendments by registration history")
        resale = workflow.index("- name: Reconcile resale-only S-1 registrations before daily regeneration")
        tests = workflow.index("- name: Run unit tests")
        pipeline = workflow.index("- name: Run daily pipeline")

        self.assertEqual([policy, history, resale, tests, pipeline], sorted([policy, history, resale, tests, pipeline]))
        self.assertIn(
            "python s1_registration_history_gate.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            workflow[history:resale],
        )
        self.assertIn(
            "python resale_registration_sanitizer.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            workflow[resale:tests],
        )
        required_env = "SEC_EDGAR_USER_AGENT: ${{ secrets.SEC_EDGAR_USER_AGENT }}"
        self.assertIn(required_env, workflow[history:resale])
        self.assertIn(required_env, workflow[resale:tests])

    def test_daily_rechecks_resale_cover_after_regeneration(self):
        workflow = DAILY_WORKFLOW.read_text(encoding="utf-8")

        pipeline = workflow.index("- name: Run daily pipeline")
        history = workflow.index("- name: Reconcile regenerated S-1 registration history")
        resale = workflow.index("- name: Reconcile resale-only S-1 registrations after daily regeneration")
        substantive = workflow.index("- name: Exclude non-substantive S-1 form templates after daily regeneration")

        self.assertEqual(
            [pipeline, history, resale, substantive],
            sorted([pipeline, history, resale, substantive]),
        )
        self.assertIn(
            "python resale_registration_sanitizer.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            workflow[resale:substantive],
        )
        required_env = "SEC_EDGAR_USER_AGENT: ${{ secrets.SEC_EDGAR_USER_AGENT }}"
        self.assertIn(required_env, workflow[resale:substantive])


if __name__ == "__main__":
    unittest.main()

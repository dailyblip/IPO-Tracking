import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily.yml"


class DailyS1HistoryGateOrderTests(unittest.TestCase):
    def test_registration_history_gate_runs_after_daily_regeneration(self):
        workflow = DAILY_WORKFLOW.read_text(encoding="utf-8")
        regeneration_step = workflow.index("- name: Run daily pipeline")
        history_gate_step = workflow.index("- name: Reconcile regenerated S-1 registration history")
        next_release_step = workflow.index("- name: Clear market quotes not refreshed in this run")

        self.assertLess(regeneration_step, history_gate_step)
        self.assertLess(history_gate_step, next_release_step)

        next_step = workflow.find("\n      - name:", history_gate_step + 1)
        gate_block = workflow[history_gate_step:] if next_step == -1 else workflow[history_gate_step:next_step]
        self.assertIn(
            "python s1_registration_history_gate.py ../docs/data/s1_watch.json ../docs/data/filings.json",
            gate_block,
        )
        self.assertIn("SEC_EDGAR_USER_AGENT: ${{ secrets.SEC_EDGAR_USER_AGENT }}", gate_block)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKFILL_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "backfill.yml"


class HistoricalBackfillWorkflowTests(unittest.TestCase):
    def test_pre_june_backfills_apply_historical_minimum_after_value_reconciliation(self):
        workflow = BACKFILL_WORKFLOW.read_text(encoding="utf-8")

        value_step = workflow.index("- name: Preserve authoritative final offering aggregates")
        historical_step = workflow.index("- name: Preserve pre-any-size historical publication threshold")
        generated_tests = workflow.index("- name: Run release-blocking regression suite on generated feed")

        self.assertLess(value_step, historical_step)
        self.assertLess(historical_step, generated_tests)
        self.assertIn('if [[ "$BACKFILL_START" < "2026-06-01" ]]; then', workflow)
        self.assertIn('HISTORICAL_END="2026-05-31"', workflow)
        self.assertIn(
            'python historical_backfill_policy.py ../docs/data/filings.json --start "$BACKFILL_START" --end "$HISTORICAL_END"',
            workflow,
        )

    def test_go_forward_backfills_do_not_reapply_historical_minimum(self):
        workflow = BACKFILL_WORKFLOW.read_text(encoding="utf-8")
        historical_step = workflow.index("- name: Preserve pre-any-size historical publication threshold")
        next_step = workflow.index("\n      - name:", historical_step + 1)
        block = workflow[historical_step:next_step]

        self.assertIn('if [[ "$BACKFILL_START" < "2026-06-01" ]]; then', block)
        self.assertIn("Backfill starts under the any-size policy; no historical minimum applied.", block)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKFILL_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "backfill.yml"


class ManualBackfillOwnershipGuardTests(unittest.TestCase):
    def test_manual_backfill_defers_to_active_ownership_refresh_before_commit(self):
        workflow = BACKFILL_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("actions: read", workflow)
        publish_step = workflow.index("- name: Publish Research Monitor data")
        publish_block = workflow[publish_step:]
        guard = publish_block.index("actions/workflows/ownership-refresh.yml/runs?per_page=100")
        commit = publish_block.index('git commit -m "Backfill Research Monitor data through $BACKFILL_END"')

        self.assertLess(guard, commit)
        self.assertIn('select(.status != "completed")', publish_block[guard:commit])
        self.assertIn("Ownership history refresh is queued or running; deferring historical backfill publication.", publish_block[guard:commit])
        self.assertIn("exit 0", publish_block[guard:commit])
        self.assertIn("GH_TOKEN: ${{ github.token }}", publish_block)

    def test_manual_backfill_remains_manual_only(self):
        workflow = BACKFILL_WORKFLOW.read_text(encoding="utf-8")
        trigger_block = workflow.split("permissions:", 1)[0]

        self.assertIn("  workflow_dispatch:", trigger_block)
        self.assertNotIn("  schedule:", trigger_block)
        self.assertNotIn("  push:", trigger_block)
        self.assertNotIn("  workflow_run:", trigger_block)


if __name__ == "__main__":
    unittest.main()

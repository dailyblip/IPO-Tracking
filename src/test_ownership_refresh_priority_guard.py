import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily.yml"


class OwnershipRefreshPriorityGuardTests(unittest.TestCase):
    def test_daily_publish_defers_to_active_ownership_refresh_before_commit(self):
        workflow = DAILY_WORKFLOW.read_text(encoding="utf-8")
        publish_start = workflow.index("- name: Publish Research Monitor data")
        publish_block = workflow[publish_start:]

        self.assertIn("actions: read", workflow)
        self.assertIn("GH_TOKEN: ${{ github.token }}", publish_block)
        self.assertIn(
            "actions/workflows/ownership-refresh.yml/runs?per_page=100",
            publish_block,
        )
        self.assertIn('select(.status != "completed")', publish_block)
        self.assertIn(
            "Ownership history refresh is queued or running; deferring Research Monitor publication.",
            publish_block,
        )

        stale_guard = publish_block.index('git rev-parse origin/main')
        ownership_guard = publish_block.index("ownership_active=")
        commit = publish_block.index('git commit -m "Update Research Monitor data"')
        self.assertLess(stale_guard, ownership_guard)
        self.assertLess(ownership_guard, commit)

        guard_exit = publish_block.index("exit 0", ownership_guard)
        self.assertLess(guard_exit, commit)


if __name__ == "__main__":
    unittest.main()

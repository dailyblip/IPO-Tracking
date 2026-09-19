import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ALERT_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "research-alerts.yml"


class ResearchAlertWorkflowContractTests(unittest.TestCase):
    def setUp(self):
        self.workflow = ALERT_WORKFLOW.read_text(encoding="utf-8")

    def test_alert_writer_uses_shared_feed_writer_queue(self):
        self.assertIn("group: research-monitor-feed-writers", self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)
        self.assertIn("queue: max", self.workflow)

    def test_alert_publication_defers_to_active_ownership_refresh(self):
        publish_step = self.workflow.index("- name: Publish alert feed and state")
        publish_block = self.workflow[publish_step:]
        ownership_check = (
            'gh api "repos/${GITHUB_REPOSITORY}/actions/workflows/'
            'ownership-refresh.yml/runs?per_page=100"'
        )
        ownership_position = publish_block.index(ownership_check)
        commit_position = publish_block.index('git commit -m "Update Research Monitor alerts"')

        self.assertIn("actions: read", self.workflow)
        self.assertIn("GH_TOKEN: ${{ github.token }}", publish_block)
        self.assertIn('select(.status != "completed")', publish_block)
        self.assertIn(
            "Ownership history refresh is queued or running; deferring Research Monitor alert publication.",
            publish_block,
        )
        self.assertLess(ownership_position, commit_position)


if __name__ == "__main__":
    unittest.main()

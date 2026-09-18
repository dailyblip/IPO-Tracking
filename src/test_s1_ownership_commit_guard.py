import re
import unittest
from pathlib import Path


class S1OwnershipCommitGuardTests(unittest.TestCase):
    def _workflow_text(self):
        return (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "s1-watch.yml"
        ).read_text(encoding="utf-8")

    def test_s1_publisher_defers_to_ownership_refresh_before_commit(self):
        workflow = self._workflow_text()

        self.assertIn("actions: read", workflow)
        guard = "actions/workflows/ownership-refresh.yml/runs?per_page=100"
        stale_check = "main advanced during this run; skipping stale S-1 publication."
        commit = 'git commit -m "Update S-1 pre-pricing watch data"'
        self.assertIn(guard, workflow)
        self.assertIn('select(.status != "completed")', workflow)
        self.assertIn(
            "Ownership history refresh is queued or running; deferring S-1 Research Monitor publication.",
            workflow,
        )
        self.assertLess(workflow.index(stale_check), workflow.index(guard))
        self.assertLess(workflow.index(guard), workflow.index(commit))

    def test_s1_ownership_guard_authenticates_github_cli(self):
        workflow = self._workflow_text()
        publish_marker = "      - name: Publish S-1 watch and researcher queue data\n"
        self.assertIn(publish_marker, workflow)
        publish_step = workflow.split(publish_marker, 1)[1]
        token = "GH_TOKEN: ${{ github.token }}"
        guard_call = 'gh api "repos/${GITHUB_REPOSITORY}/actions/workflows/ownership-refresh.yml/runs?per_page=100"'
        self.assertIn(token, publish_step)
        self.assertIn(guard_call, publish_step)
        self.assertLess(
            publish_step.index(token),
            publish_step.index(guard_call),
            "S-1 publish step must authenticate GitHub CLI before checking ownership runs",
        )

    def test_s1_update_feed_has_sec_processing_timeout_headroom(self):
        workflow = self._workflow_text()
        update_feed = workflow.split("\n  update-feed:\n", 1)[1]
        match = re.search(r"^    timeout-minutes:\s*(\d+)\s*$", update_feed, re.MULTILINE)
        self.assertIsNotNone(match, "update-feed must set an explicit timeout")
        self.assertGreaterEqual(
            int(match.group(1)),
            45,
            "S-1 release pipeline needs headroom for bounded SEC network checks",
        )


if __name__ == "__main__":
    unittest.main()

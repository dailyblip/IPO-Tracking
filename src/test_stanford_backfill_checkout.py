import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "stanford-backfill-once.yml"


class StanfordBackfillCheckoutTests(unittest.TestCase):
    def test_replay_starts_from_latest_main_after_writer_queue(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        checkout_start = workflow.index("- name: Check out repo")
        checkout_end = workflow.index("- name: Set up Python", checkout_start)
        checkout_block = workflow[checkout_start:checkout_end]

        self.assertIn("group: research-monitor-feed-writers", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("ref: main", checkout_block)
        self.assertIn("fetch-depth: 0", checkout_block)

    def test_replay_still_fails_closed_if_main_advances_during_run(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        publish_start = workflow.index("- name: Publish Research Monitor data")
        publish_block = workflow[publish_start:]

        self.assertIn("git fetch origin main", publish_block)
        self.assertIn(
            'if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then',
            publish_block,
        )
        self.assertIn(
            "main advanced during this run; refusing stale Stanford backfill publication.",
            publish_block,
        )
        self.assertIn("exit 1", publish_block)
        self.assertNotIn("git pull --rebase", publish_block)


if __name__ == "__main__":
    unittest.main()

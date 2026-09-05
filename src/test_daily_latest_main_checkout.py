import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily.yml"


class DailyLatestMainCheckoutTests(unittest.TestCase):
    def test_daily_writer_starts_from_latest_main_after_shared_queue(self):
        workflow = DAILY_WORKFLOW.read_text(encoding="utf-8")
        checkout_start = workflow.index("- name: Check out repo")
        checkout_end = workflow.find("\n      - name:", checkout_start + 1)
        checkout_block = (
            workflow[checkout_start:]
            if checkout_end == -1
            else workflow[checkout_start:checkout_end]
        )

        self.assertIn("ref: main", checkout_block)
        self.assertIn("fetch-depth: 0", checkout_block)

        publish_start = workflow.index("- name: Publish Research Monitor data")
        publish_block = workflow[publish_start:]
        self.assertIn("git fetch origin main", publish_block)
        self.assertIn(
            'if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then',
            publish_block,
        )
        self.assertIn(
            "main advanced during this run; skipping stale feed publication.",
            publish_block,
        )


if __name__ == "__main__":
    unittest.main()

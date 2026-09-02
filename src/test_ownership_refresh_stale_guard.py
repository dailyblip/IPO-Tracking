import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ownership-refresh.yml"


class OwnershipRefreshStaleGuardTests(unittest.TestCase):
    def test_queued_refresh_starts_from_latest_main_and_fails_closed_if_main_advances(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        checkout_start = workflow.index("- uses: actions/checkout@v4")
        checkout_end = workflow.index("\n      - uses: actions/setup-python@v5", checkout_start)
        checkout_block = workflow[checkout_start:checkout_end]
        self.assertIn("ref: main", checkout_block)
        self.assertIn("fetch-depth: 0", checkout_block)

        publish_start = workflow.index("- name: Publish refreshed ownership data")
        publish_block = workflow[publish_start:]
        stale_check = 'if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then'
        stale_start = publish_block.index(stale_check)
        stale_end = publish_block.index("\n          fi", stale_start)
        stale_block = publish_block[stale_start:stale_end]

        self.assertIn(
            "main advanced during this run; refusing stale ownership publication.",
            stale_block,
        )
        self.assertIn("exit 1", stale_block)
        self.assertNotIn("exit 0", stale_block)
        self.assertNotIn("git pull --rebase", workflow)


if __name__ == "__main__":
    unittest.main()

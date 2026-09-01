import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
S1_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "s1-watch.yml"


class S1StalePublicationGuardTests(unittest.TestCase):
    def test_s1_writer_skips_stale_generated_feed_instead_of_rebasing(self):
        workflow = S1_WORKFLOW.read_text(encoding="utf-8")
        publish_step = workflow.index("- name: Publish S-1 watch and researcher queue data")
        publish_block = workflow[publish_step:]

        self.assertIn("git fetch origin main", publish_block)
        self.assertIn('"$(git rev-parse HEAD)" != "$(git rev-parse origin/main)"', publish_block)
        self.assertIn("main advanced during this run; skipping stale S-1 publication.", publish_block)
        self.assertNotIn("git pull --rebase origin main", publish_block)


if __name__ == "__main__":
    unittest.main()

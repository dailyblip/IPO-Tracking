import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily.yml"


class DailyWorkflowTimeoutTests(unittest.TestCase):
    def test_daily_release_chain_has_sixty_minute_headroom(self):
        workflow = DAILY_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("timeout-minutes: 60", workflow)
        self.assertNotIn("timeout-minutes: 30", workflow)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OWNERSHIP_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ownership-refresh.yml"


class LockupRefreshTriggerTests(unittest.TestCase):
    def test_lockup_parser_changes_trigger_historical_refresh(self):
        workflow = OWNERSHIP_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("- 'src/lockup_parser.py'", workflow)
        self.assertIn("- 'src/test_lockup_parser.py'", workflow)


if __name__ == "__main__":
    unittest.main()

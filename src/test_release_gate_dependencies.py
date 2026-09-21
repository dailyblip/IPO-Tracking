import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = REPO_ROOT / "requirements.txt"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"


class ReleaseGateDependencyTests(unittest.TestCase):
    def test_pytest_is_installed_for_generated_feed_release_gates(self):
        package_names = set()
        for raw_line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            package_names.add(re.split(r"[<>=!~;\[]", line, maxsplit=1)[0].lower())

        self.assertIn("pytest", package_names)

        for workflow_name in ("daily.yml", "ownership-refresh.yml"):
            workflow = (WORKFLOW_DIR / workflow_name).read_text(encoding="utf-8")
            with self.subTest(workflow=workflow_name):
                self.assertIn("python -m pytest src -q", workflow)


if __name__ == "__main__":
    unittest.main()

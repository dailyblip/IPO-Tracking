import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ownership-refresh.yml"


class OwnershipRefreshOfferingValueWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_reconciles_authoritative_offering_value_before_golden_validation(self):
        reconcile = self.workflow.index("- name: Preserve authoritative final offering aggregates")
        golden = self.workflow.index("- name: Validate regenerated golden records")

        self.assertLess(reconcile, golden)
        self.assertIn(
            "python offering_value_reconciler.py ../docs/data/filings.json",
            self.workflow[reconcile:golden],
        )
        self.assertIn("SEC_EDGAR_USER_AGENT: ${{ secrets.SEC_EDGAR_USER_AGENT }}", self.workflow[reconcile:golden])

    def test_reconciler_changes_retrigger_ownership_refresh(self):
        for path in (
            "src/offering_value_reconciler.py",
            "src/test_offering_value_reconciler.py",
        ):
            with self.subTest(path=path):
                self.assertIn(f"- '{path}'", self.workflow)


if __name__ == "__main__":
    unittest.main()

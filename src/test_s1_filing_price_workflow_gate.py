import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
S1_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "s1-watch.yml"


class S1FilingPriceWorkflowGateTests(unittest.TestCase):
    def test_s1_writer_runs_filing_price_history_before_publication(self):
        workflow = S1_WORKFLOW.read_text(encoding="utf-8")

        update_step = workflow.index("- name: Update pre-pricing S-1 feed")
        policy_step = workflow.index("- name: Enforce public-feed eligibility policy")
        price_history_step = workflow.index(
            "- name: Recover authoritative preliminary filing-price ranges"
        )
        publish_step = workflow.index("- name: Publish S-1 watch and researcher queue data")

        self.assertLess(update_step, policy_step)
        self.assertLess(policy_step, price_history_step)
        self.assertLess(price_history_step, publish_step)
        self.assertIn(
            "python filing_price_history.py ../docs/data/filings.json",
            workflow[price_history_step:publish_step],
        )

    def test_s1_pr_validation_reacts_to_filing_price_history_changes(self):
        workflow = S1_WORKFLOW.read_text(encoding="utf-8")
        trigger_block = workflow.split("  push:", 1)[0]
        test_step = workflow.index("- name: Run S-1 monitor tests")
        update_job = workflow.index("  update-feed:")
        test_block = workflow[test_step:update_job]

        self.assertIn("- 'src/filing_price_history.py'", trigger_block)
        self.assertIn("- 'src/test_filing_price_history.py'", trigger_block)
        self.assertIn("test_filing_price_history.py", test_block)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class WorkflowContractTests(unittest.TestCase):
    def test_ownership_refresh_has_no_offering_size_publication_gate(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "ownership-refresh.yml").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("100_000_000", workflow)
        self.assertNotIn("MINIMUM_IPO_VALUE", workflow)
        self.assertNotIn("float(filing.get('value')", workflow)

    def test_ownership_refresh_applies_public_feed_policy_before_validation(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "ownership-refresh.yml").read_text(
            encoding="utf-8"
        )

        policy_step = workflow.index("- name: Enforce public-feed eligibility policy")
        validation_step = workflow.index("- name: Validate public feed")
        self.assertLess(policy_step, validation_step)


if __name__ == "__main__":
    unittest.main()

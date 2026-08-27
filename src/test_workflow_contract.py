import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
OWNERSHIP_WORKFLOW = WORKFLOW_DIR / "ownership-refresh.yml"
S1_WORKFLOW = WORKFLOW_DIR / "s1-watch.yml"
SHARED_FEED_WRITER_WORKFLOWS = [
    WORKFLOW_DIR / "daily.yml",
    WORKFLOW_DIR / "s1-watch.yml",
    WORKFLOW_DIR / "ownership-refresh.yml",
    WORKFLOW_DIR / "backfill.yml",
    WORKFLOW_DIR / "stanford-backfill-once.yml",
]


def _workflow(path):
    return path.read_text(encoding="utf-8")


def _ownership_workflow():
    return _workflow(OWNERSHIP_WORKFLOW)


class WorkflowContractTests(unittest.TestCase):
    def test_ownership_refresh_has_no_offering_size_publication_gate(self):
        workflow = _ownership_workflow()

        self.assertNotIn("100_000_000", workflow)
        self.assertNotIn("MINIMUM_IPO_VALUE", workflow)
        self.assertNotIn("float(filing.get('value')", workflow)

    def test_ownership_refresh_applies_public_feed_policy_before_validation(self):
        workflow = _ownership_workflow()

        policy_step = workflow.index("- name: Enforce public-feed eligibility policy")
        validation_step = workflow.index("- name: Validate public feed")
        self.assertLess(policy_step, validation_step)

    def test_ownership_refresh_runs_release_safety_chain_before_validation(self):
        workflow = _ownership_workflow()
        ordered_steps = [
            "- name: Reconcile final 424B4 lifecycle transitions",
            "- name: Sanitize impossible lifecycle dates",
            "- name: Remove post-reporting follow-on/resale offerings",
            "- name: Enforce public-feed eligibility policy",
            "- name: Recover authoritative preliminary filing-price ranges",
            "- name: Remove market quotes from pre-pricing records",
            "- name: Validate public feed",
        ]

        positions = [workflow.index(step) for step in ordered_steps]
        self.assertEqual(positions, sorted(positions))

    def test_ownership_refresh_reacts_to_release_safety_code_changes(self):
        workflow = _ownership_workflow()
        required_paths = [
            "src/lifecycle_reconciler.py",
            "src/lifecycle_date_sanitizer.py",
            "src/followon_sanitizer.py",
            "src/prepricing_quote_sanitizer.py",
            "src/test_lifecycle_reconciler.py",
            "src/test_lifecycle_date_sanitizer.py",
            "src/test_followon_sanitizer.py",
            "src/test_prepricing_quote_sanitizer.py",
        ]

        for path in required_paths:
            with self.subTest(path=path):
                self.assertIn(f"- '{path}'", workflow)

    def test_ownership_refresh_validation_blocks_impossible_release_states(self):
        workflow = _ownership_workflow()

        self.assertIn("Pre-pricing record has a live market quote", workflow)
        self.assertIn("Impossible lifecycle chronology", workflow)
        self.assertIn("filing.get('current_price') not in (None, '')", workflow)

    def test_shared_feed_writers_queue_instead_of_replacing_pending_runs(self):
        for path in SHARED_FEED_WRITER_WORKFLOWS:
            workflow = _workflow(path)
            with self.subTest(workflow=path.name):
                self.assertIn("group: research-monitor-feed-writers", workflow)
                self.assertIn("cancel-in-progress: false", workflow)
                self.assertIn("queue: max", workflow)

    def test_s1_release_gate_allows_unknown_size_but_checks_published_values(self):
        workflow = _workflow(S1_WORKFLOW)

        self.assertIn("raw_value = filing.get('value')", workflow)
        self.assertIn("if raw_value in (None, ''):", workflow)
        self.assertIn("populated offering size is missing source provenance", workflow)
        self.assertIn("populated offering-size confidence must be High", workflow)


if __name__ == "__main__":
    unittest.main()

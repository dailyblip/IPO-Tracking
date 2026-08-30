import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
DAILY_WORKFLOW = WORKFLOW_DIR / "daily.yml"
OWNERSHIP_WORKFLOW = WORKFLOW_DIR / "ownership-refresh.yml"
S1_WORKFLOW = WORKFLOW_DIR / "s1-watch.yml"
TEST_WORKFLOW = WORKFLOW_DIR / "test.yml"
REPO_STEWARD_WORKFLOW = WORKFLOW_DIR / "repo-steward.yml"
PUBLIC_FEED_POLICY_WORKFLOWS = [
    DAILY_WORKFLOW,
    S1_WORKFLOW,
    OWNERSHIP_WORKFLOW,
]
PRETEST_POLICY_RECONCILIATION_WORKFLOWS = [
    DAILY_WORKFLOW,
    OWNERSHIP_WORKFLOW,
    TEST_WORKFLOW,
]
SHARED_FEED_WRITER_WORKFLOWS = [
    DAILY_WORKFLOW,
    S1_WORKFLOW,
    OWNERSHIP_WORKFLOW,
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

    def test_policy_sensitive_workflows_reconcile_checked_in_feed_before_unit_tests(self):
        pretest_marker = "- name: Reconcile checked-in feed with current release policy"
        unit_test_marker = "- name: Run unit tests"
        required_env = "SEC_EDGAR_USER_AGENT: ${{ secrets.SEC_EDGAR_USER_AGENT }}"
        policy_command = "python public_feed_policy.py ../docs/data/filings.json"

        for path in PRETEST_POLICY_RECONCILIATION_WORKFLOWS:
            workflow = _workflow(path)
            pretest_step = workflow.index(pretest_marker)
            unit_test_step = workflow.index(unit_test_marker)
            next_step = workflow.find("\n      - name:", pretest_step + len(pretest_marker))
            block = workflow[pretest_step:] if next_step == -1 else workflow[pretest_step:next_step]
            with self.subTest(workflow=path.name):
                self.assertLess(pretest_step, unit_test_step)
                self.assertIn(policy_command, block)
                self.assertIn(required_env, block)

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

    def test_daily_writer_defers_live_golden_until_after_regeneration(self):
        workflow = _workflow(DAILY_WORKFLOW)
        unit_test_step = workflow.index("- name: Run unit tests")
        refresh_step = workflow.index("- name: Run daily pipeline")
        golden_step = workflow.index("- name: Validate refreshed golden records")
        publish_step = workflow.index("- name: Publish Research Monitor data")
        next_step = workflow.find("\n      - name:", unit_test_step + 1)
        unit_test_block = workflow[unit_test_step:next_step]

        self.assertIn("SKIP_LIVE_GOLDEN: '1'", unit_test_block)
        self.assertLess(unit_test_step, refresh_step)
        self.assertLess(refresh_step, golden_step)
        self.assertLess(golden_step, publish_step)
        self.assertIn("test_golden_records.py", workflow[golden_step:publish_step])

    def test_repo_steward_reports_agent_failure_without_failing_again(self):
        workflow = _workflow(REPO_STEWARD_WORKFLOW)

        self.assertIn("continue-on-error: true", workflow)
        self.assertIn("agent_failed: ${{ steps.agent_status.outputs.agent_failed }}", workflow)
        self.assertIn("needs.generate_fix.outputs.agent_failed == 'true'", workflow)
        self.assertIn('gh issue comment "$INCIDENT_NUMBER" --repo "$GITHUB_REPOSITORY"', workflow)

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

    def test_public_feed_policy_steps_have_sec_user_agent(self):
        marker = "- name: Enforce public-feed eligibility policy"
        required_env = "SEC_EDGAR_USER_AGENT: ${{ secrets.SEC_EDGAR_USER_AGENT }}"

        for path in PUBLIC_FEED_POLICY_WORKFLOWS:
            workflow = _workflow(path)
            start = workflow.index(marker)
            next_step = workflow.find("\n      - name:", start + len(marker))
            block = workflow[start:] if next_step == -1 else workflow[start:next_step]
            with self.subTest(workflow=path.name):
                self.assertIn(required_env, block)

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

    def test_s1_watch_reacts_to_cover_price_parser_changes(self):
        s1_workflow = _workflow(S1_WORKFLOW)
        daily_workflow = _workflow(DAILY_WORKFLOW)
        required_paths = [
            "src/filing_parser.py",
            "src/test_cover_price_context.py",
        ]

        # PRs that touch the parser still run the focused S-1 regression suite.
        for path in required_paths:
            with self.subTest(path=path):
                self.assertIn(f"- '{path}'", s1_workflow)
        self.assertIn("test_cover_price_context.py", s1_workflow)

        # On main, source changes trigger Daily via src/**; the S-1 writer then
        # follows that successful run instead of racing it for the shared writer lock.
        self.assertIn("- 'src/**'", daily_workflow)
        self.assertIn("workflow_run:", s1_workflow)
        self.assertIn("- Daily IPO Tracker", s1_workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", s1_workflow)
        workflow_run_start = s1_workflow.index("  workflow_run:")
        dispatch_start = s1_workflow.index("  workflow_dispatch:")
        workflow_run_block = s1_workflow[workflow_run_start:dispatch_start]
        self.assertIn("branches:\n      - main", workflow_run_block)
        push_start = s1_workflow.index("  push:")
        push_block = s1_workflow[push_start:workflow_run_start]
        for path in required_paths:
            with self.subTest(push_path=path):
                self.assertNotIn(f"- '{path}'", push_block)


if __name__ == "__main__":
    unittest.main()

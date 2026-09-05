import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OWNERSHIP_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ownership-refresh.yml"


def _workflow():
    return OWNERSHIP_WORKFLOW.read_text(encoding="utf-8")


class OwnershipRefreshGoldenOrderingTests(unittest.TestCase):
    def test_live_golden_check_runs_only_after_regenerated_feed(self):
        workflow = _workflow()
        unit_marker = "- name: Run unit tests"
        refresh_marker = "- name: Refresh qualifying IPO history and Stanford affiliations"
        golden_marker = "- name: Validate regenerated golden records"
        validate_marker = "- name: Validate public feed"
        publish_marker = "- name: Publish refreshed ownership data"

        unit_pos = workflow.index(unit_marker)
        refresh_pos = workflow.index(refresh_marker)
        golden_pos = workflow.index(golden_marker)
        validate_pos = workflow.index(validate_marker)
        publish_pos = workflow.index(publish_marker)

        self.assertLess(unit_pos, refresh_pos)
        self.assertLess(refresh_pos, golden_pos)
        self.assertLess(golden_pos, validate_pos)
        self.assertLess(validate_pos, publish_pos)

        pre_refresh_block = workflow[unit_pos:refresh_pos]
        self.assertIn("SKIP_LIVE_GOLDEN: '1'", pre_refresh_block)

        golden_block = workflow[golden_pos:validate_pos]
        self.assertIn(
            "python -m unittest discover -s src -p 'test_golden_records.py' -v",
            golden_block,
        )
        self.assertNotIn("SKIP_LIVE_GOLDEN", golden_block)

    def test_regenerated_feed_runs_full_release_suite_before_publish(self):
        workflow = _workflow()
        history_marker = "- name: Recover authoritative preliminary filing-price ranges"
        quote_marker = "- name: Verify market quote issuer identity"
        regression_marker = "- name: Run release-blocking regression suite on regenerated feed"
        golden_marker = "- name: Validate regenerated golden records"
        publish_marker = "- name: Publish refreshed ownership data"

        history_pos = workflow.index(history_marker)
        quote_pos = workflow.index(quote_marker)
        regression_pos = workflow.index(regression_marker)
        golden_pos = workflow.index(golden_marker)
        publish_pos = workflow.index(publish_marker)

        self.assertLess(history_pos, quote_pos)
        self.assertLess(quote_pos, regression_pos)
        self.assertLess(regression_pos, golden_pos)
        self.assertLess(regression_pos, publish_pos)

        next_step = workflow.find("\n      - name:", regression_pos + 1)
        regression_block = (
            workflow[regression_pos:]
            if next_step == -1
            else workflow[regression_pos:next_step]
        )
        self.assertIn("SKIP_LIVE_GOLDEN: '1'", regression_block)
        self.assertIn(
            "python -m unittest discover -s src -p 'test_*.py' -v",
            regression_block,
        )


if __name__ == "__main__":
    unittest.main()

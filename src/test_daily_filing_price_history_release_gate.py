import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily.yml"


class DailyFilingPriceHistoryReleaseGateTests(unittest.TestCase):
    def test_priced_blank_filing_price_history_review_precedes_release_and_publish(self):
        workflow = DAILY_WORKFLOW.read_text(encoding="utf-8")

        lifecycle_step = workflow.index(
            "- name: Reconcile final 424B4 lifecycle transitions"
        )
        history_step = workflow.index(
            "- name: Recover authoritative preliminary filing-price ranges"
        )
        release_step = workflow.index(
            "- name: Run release-blocking regression suite on generated feed"
        )
        publish_step = workflow.index("- name: Publish Research Monitor data")
        next_step = workflow.find("\n      - name:", history_step + 1)
        history_block = (
            workflow[history_step:]
            if next_step == -1
            else workflow[history_step:next_step]
        )

        # Lifecycle promotion can create a priced 424B4 with a blank Filing Price.
        # The SEC S-1/S-1A history pass must run before a blank can reach release
        # validation or publication.
        self.assertLess(lifecycle_step, history_step)
        self.assertLess(history_step, release_step)
        self.assertLess(history_step, publish_step)
        self.assertIn(
            "python filing_price_history.py ../docs/data/filings.json",
            history_block,
        )
        self.assertIn(
            "SEC_EDGAR_USER_AGENT: ${{ secrets.SEC_EDGAR_USER_AGENT }}",
            history_block,
        )


if __name__ == "__main__":
    unittest.main()

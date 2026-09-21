import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "s1-watch.yml"


class S1QuoteReleaseContractTests(unittest.TestCase):
    def test_market_quote_release_gate_changes_trigger_s1_monitor(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        pull_request_start = workflow.index("  pull_request:")
        push_start = workflow.index("\n  # Source changes", pull_request_start)
        pull_request_block = workflow[pull_request_start:push_start]

        self.assertIn(
            "      - 'src/market_quote_release_gate.py'",
            pull_request_block,
        )

    def test_s1_writer_revalidates_quote_identity_before_release(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        update_step = workflow.index("- name: Update pre-pricing S-1 feed")
        filing_price_step = workflow.index(
            "- name: Recover authoritative preliminary filing-price ranges"
        )
        quote_step = workflow.index("- name: Verify market quote issuer identity")
        regression_step = workflow.index(
            "- name: Run release-blocking regression suite on generated feed"
        )
        publish_step = workflow.index(
            "- name: Publish S-1 watch and researcher queue data"
        )

        self.assertEqual(
            [update_step, filing_price_step, quote_step, regression_step, publish_step],
            sorted([update_step, filing_price_step, quote_step, regression_step, publish_step]),
        )

        next_step = workflow.find("\n      - name:", quote_step + 1)
        quote_block = workflow[quote_step:] if next_step == -1 else workflow[quote_step:next_step]
        self.assertIn(
            "python market_quote_release_gate.py ../docs/data/filings.json",
            quote_block,
        )
        self.assertIn(
            "MARKET_DATA_API_KEY: ${{ secrets.MARKET_DATA_API_KEY }}",
            quote_block,
        )
        self.assertIn(
            "SEC_EDGAR_USER_AGENT: ${{ secrets.SEC_EDGAR_USER_AGENT }}",
            quote_block,
        )


if __name__ == "__main__":
    unittest.main()

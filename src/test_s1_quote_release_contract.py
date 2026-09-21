import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "s1-watch.yml"


class S1QuoteReleaseContractTests(unittest.TestCase):
    def test_quote_release_dependencies_trigger_s1_monitor(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        pull_request_start = workflow.index("  pull_request:")
        push_start = workflow.index("\n  # Source changes", pull_request_start)
        pull_request_block = workflow[pull_request_start:push_start]

        required_paths = (
            "src/final_ticker_reconciler.py",
            "src/test_final_ticker_reconciler.py",
            "src/market_price_freshness_gate.py",
            "src/test_market_price_freshness_gate.py",
            "src/market_quote_identity.py",
            "src/test_market_quote_identity.py",
            "src/market_quote_release_gate.py",
            "src/test_market_quote_release_gate.py",
            "src/test_market_quote_sec_crosscheck.py",
        )
        for path in required_paths:
            with self.subTest(path=path):
                self.assertIn(f"      - '{path}'", pull_request_block)

    def test_quote_release_dependencies_run_in_focused_s1_tests(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        test_step = workflow.index("- name: Run S-1 monitor tests")
        next_step = workflow.index("\n\n  update-feed:", test_step)
        test_block = workflow[test_step:next_step]

        for module in (
            "test_final_ticker_reconciler.py",
            "test_market_price_freshness_gate.py",
            "test_market_quote_identity.py",
            "test_market_quote_release_gate.py",
            "test_market_quote_sec_crosscheck.py",
        ):
            with self.subTest(module=module):
                self.assertIn(module, test_block)

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

import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ownership-refresh.yml"


class OwnershipQuoteReleaseContractTests(unittest.TestCase):
    def test_ownership_writer_revalidates_quote_identity_before_validation_and_publish(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        prepricing_step = workflow.index("- name: Remove market quotes from pre-pricing records")
        quote_step = workflow.index("- name: Verify market quote issuer identity")
        regression_step = workflow.index(
            "- name: Run release-blocking regression suite on regenerated feed"
        )
        validation_step = workflow.index("- name: Validate public feed")
        publish_step = workflow.index("- name: Publish refreshed ownership data")

        self.assertEqual(
            [prepricing_step, quote_step, regression_step, validation_step, publish_step],
            sorted(
                [
                    prepricing_step,
                    quote_step,
                    regression_step,
                    validation_step,
                    publish_step,
                ]
            ),
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

    def test_ownership_refresh_reacts_to_quote_safety_changes(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        required_paths = [
            "src/market_quote_identity.py",
            "src/market_quote_release_gate.py",
            "src/market_price_freshness_gate.py",
            "src/test_market_quote_identity.py",
            "src/test_market_quote_release_gate.py",
            "src/test_market_price_freshness_gate.py",
        ]

        for path in required_paths:
            with self.subTest(path=path):
                self.assertIn(f"- '{path}'", workflow)


if __name__ == "__main__":
    unittest.main()

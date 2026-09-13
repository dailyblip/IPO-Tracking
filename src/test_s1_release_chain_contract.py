import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
S1_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "s1-watch.yml"


class S1ReleaseChainContractTests(unittest.TestCase):
    def test_s1_writer_runs_release_safety_chain_before_publication(self):
        """Keep the S-1 writer from drifting around the priority-3 release gates.

        The S-1 monitor writes both the dedicated watch and the public Research
        Monitor queue. Any future workflow edit must therefore preserve the SEC
        ticker/registration checks, Filing Price recovery, canonical public-feed
        policy, and generated-feed regression suite before those files can commit.
        """
        workflow = S1_WORKFLOW.read_text(encoding="utf-8")
        update_step = workflow.index("- name: Update pre-pricing S-1 feed")
        ordered_steps = [
            "- name: Reconcile S-1 tickers from current SEC listing language",
            "- name: Verify fixed pre-pricing Filing Prices against SEC cover terms",
            "- name: Exclude resale-only S-1 amendments by registration history",
            "- name: Exclude non-substantive S-1 form templates",
            "- name: Check archived SEC reporting history",
            "- name: Exclude resale-only S-1 registrations at release",
            "- name: Sanitize impossible lifecycle dates",
            "- name: Enforce public-feed eligibility policy",
            "- name: Recover authoritative preliminary filing-price ranges",
            "- name: Normalize issuer display names",
            "- name: Block weak offering-size provenance before publication",
            "- name: Run release-blocking regression suite on generated feed",
            "- name: Validate V1 public feed schema",
            "- name: Publish S-1 watch and researcher queue data",
        ]

        positions = [workflow.index(step) for step in ordered_steps]
        self.assertTrue(all(position > update_step for position in positions))
        self.assertEqual(positions, sorted(positions))

        self.assertIn(
            "python ticker_listing_reconciler.py ../docs/data/s1_watch.json",
            workflow,
        )
        self.assertIn(
            "python filing_price_history.py ../docs/data/filings.json",
            workflow,
        )
        self.assertIn("python -m pytest src -q", workflow)

    def test_s1_ticker_reconciler_contract_covers_public_queue_and_csv(self):
        """The workflow's watch reconciliation must also protect public surfaces."""
        reconciler = (REPO_ROOT / "src" / "ticker_listing_reconciler.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('if path.name == "s1_watch.json":', reconciler)
        self.assertIn('queue_path = path.with_name("filings.json")', reconciler)
        self.assertIn("verified_lineage = _verified_watch_tickers(watch_payload)", reconciler)
        self.assertIn("sync_csv=True", reconciler)


if __name__ == "__main__":
    unittest.main()

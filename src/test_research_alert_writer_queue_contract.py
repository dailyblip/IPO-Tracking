import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ALERT_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "research-alerts.yml"


class ResearchAlertWriterQueueContractTests(unittest.TestCase):
    def test_alert_writer_uses_shared_non_replacing_queue(self):
        workflow = ALERT_WORKFLOW.read_text(encoding="utf-8")
        concurrency_start = workflow.index("concurrency:")
        trigger_start = workflow.index("\non:", concurrency_start)
        concurrency = workflow[concurrency_start:trigger_start]

        self.assertIn("group: research-monitor-feed-writers", concurrency)
        self.assertIn("cancel-in-progress: false", concurrency)
        self.assertIn("queue: max", concurrency)

    def test_contract_is_attached_to_the_generated_alert_state_writer(self):
        workflow = ALERT_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            "git add docs/data/alerts.json docs/data/alerts_state.json", workflow
        )
        self.assertIn('git commit -m "Update Research Monitor alerts"', workflow)


if __name__ == "__main__":
    unittest.main()

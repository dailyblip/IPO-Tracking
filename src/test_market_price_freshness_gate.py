import csv
import json
import tempfile
import unittest
from pathlib import Path

from market_price_freshness_gate import sanitize_file, sanitize_payload


ROOT = Path(__file__).resolve().parents[1]
DAILY_WORKFLOW = ROOT / ".github" / "workflows" / "daily.yml"
OWNERSHIP_WORKFLOW = ROOT / ".github" / "workflows" / "ownership-refresh.yml"


class MarketPriceFreshnessGateTests(unittest.TestCase):
    def test_stale_quote_and_all_market_derivatives_are_cleared(self):
        payload = {
            "generated_at": "2026-09-01T00:06:53+00:00",
            "filings": [
                {
                    "id": "acme",
                    "company": "Acme Robotics, Inc.",
                    "ticker": "ACME",
                    "current_price": 22.0,
                    "price_updated": "2026-08-20T00:06:53+00:00",
                    "signals": [
                        "Offering priced at $18.00 per share",
                        "Largest named holding currently valued at approximately $44M",
                    ],
                    "people": [
                        {
                            "name": "Jane Founder",
                            "shares": 2_000_000,
                            "cash_value": 44_000_000,
                            "liquid_value": 11_000_000,
                            "locked_value": 33_000_000,
                            "valuation_as_of": "2026-08-20T00:06:53+00:00",
                            "ipo_value": 36_000_000,
                        }
                    ],
                }
            ],
        }

        sanitized, stale = sanitize_payload(payload)

        self.assertEqual(len(stale), 1)
        filing = sanitized["filings"][0]
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertEqual(filing["signals"], ["Offering priced at $18.00 per share"])
        person = filing["people"][0]
        for field in ("cash_value", "liquid_value", "locked_value", "valuation_as_of"):
            self.assertNotIn(field, person)
        self.assertEqual(person["ipo_value"], 36_000_000)

    def test_provider_timestamp_need_not_equal_pipeline_generated_at(self):
        payload = {
            "generated_at": "2026-09-05T08:18:00+00:00",
            "filings": [
                {
                    "company": "Acme Robotics, Inc.",
                    "ticker": "ACME",
                    "current_price": 22.0,
                    "price_updated": "2026-09-04T20:00:00+00:00",
                    "people": [
                        {
                            "name": "Jane Founder",
                            "cash_value": 44_000_000,
                            "valuation_as_of": "2026-09-04T20:00:00+00:00",
                        }
                    ],
                }
            ],
        }

        sanitized, stale = sanitize_payload(payload)

        self.assertEqual(stale, [])
        filing = sanitized["filings"][0]
        self.assertEqual(filing["current_price"], 22.0)
        self.assertEqual(filing["price_updated"], "2026-09-04T20:00:00+00:00")
        self.assertEqual(
            filing["people"][0]["valuation_as_of"], "2026-09-04T20:00:00+00:00"
        )

    def test_same_run_positive_quote_is_preserved(self):
        marker = "2026-09-01T00:06:53.558358+00:00"
        payload = {
            "generated_at": marker,
            "filings": [
                {
                    "company": "Acme Robotics, Inc.",
                    "ticker": "ACME",
                    "current_price": 22.0,
                    "price_updated": marker,
                    "people": [{"name": "Jane Founder", "cash_value": 44_000_000}],
                }
            ],
        }

        sanitized, stale = sanitize_payload(payload)

        self.assertEqual(stale, [])
        self.assertEqual(sanitized["filings"][0]["current_price"], 22.0)
        self.assertEqual(
            sanitized["filings"][0]["people"][0]["cash_value"], 44_000_000
        )

    def test_invalid_quote_is_cleared_even_when_timestamp_matches(self):
        marker = "2026-09-01T00:06:53+00:00"
        payload = {
            "generated_at": marker,
            "filings": [
                {
                    "company": "Acme Robotics, Inc.",
                    "ticker": "ACME",
                    "current_price": 0,
                    "price_updated": marker,
                    "people": [],
                }
            ],
        }

        sanitized, stale = sanitize_payload(payload)

        self.assertEqual(len(stale), 1)
        self.assertNotIn("current_price", sanitized["filings"][0])
        self.assertNotIn("price_updated", sanitized["filings"][0])

    def test_timezone_naive_provider_timestamp_is_cleared(self):
        payload = {
            "generated_at": "2026-09-05T08:18:00+00:00",
            "filings": [
                {
                    "company": "Acme Robotics, Inc.",
                    "ticker": "ACME",
                    "current_price": 22.0,
                    "price_updated": "2026-09-05T08:00:00",
                    "people": [],
                }
            ],
        }

        sanitized, stale = sanitize_payload(payload)

        self.assertEqual(len(stale), 1)
        self.assertNotIn("current_price", sanitized["filings"][0])
        self.assertNotIn("price_updated", sanitized["filings"][0])

    def test_file_gate_keeps_csv_synchronized_after_clearing_stale_quote(self):
        with tempfile.TemporaryDirectory() as directory:
            feed = Path(directory) / "filings.json"
            feed.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "generated_at": "2026-09-01T00:06:53+00:00",
                        "filings": [
                            {
                                "id": "acme",
                                "company": "Acme Robotics, Inc.",
                                "ticker": "ACME",
                                "form": "424B4",
                                "stage": "Priced",
                                "filed": "2026-09-01",
                                "current_price": 22.0,
                                "price_updated": "2026-08-20T00:06:53+00:00",
                                "people": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            stale = sanitize_file(feed)

            self.assertEqual(len(stale), 1)
            persisted = json.loads(feed.read_text(encoding="utf-8"))
            self.assertNotIn("current_price", persisted["filings"][0])
            with feed.with_suffix(".csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["current_price"], "")

    def test_full_feed_workflows_run_freshness_gate_immediately_after_main(self):
        command = "python market_price_freshness_gate.py ../docs/data/filings.json"
        lifecycle = "python lifecycle_reconciler.py ../docs/data/filings.json"
        for workflow in (DAILY_WORKFLOW, OWNERSHIP_WORKFLOW):
            with self.subTest(workflow=workflow.name):
                text = workflow.read_text(encoding="utf-8")
                main_position = text.index("python main.py")
                gate_position = text.index(command)
                lifecycle_position = text.index(lifecycle)
                self.assertLess(main_position, gate_position)
                self.assertLess(gate_position, lifecycle_position)


if __name__ == "__main__":
    unittest.main()

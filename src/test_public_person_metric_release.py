import json
import tempfile
import unittest
from pathlib import Path

from public_feed_policy import enforce_public_feed_policy


class PublicPersonMetricReleaseTests(unittest.TestCase):
    def test_release_gate_clears_stale_malformed_ownership_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "filings": [
                    {
                        "id": "standard-nuclear",
                        "company": "Standard Nuclear, Inc.",
                        "form": "424B4",
                        "filed": "2026-07-16",
                        "value": 225_000_000,
                        "people": [
                            {
                                "name": "Entities affiliated with Decisive Point Group",
                                "shares": 25_313_314.0,
                                "ownership_percent": 17.0,
                                "ownership_percent_before": 25_313_314.0,
                                "ownership_percent_after": 17.0,
                                "shares_before_ipo": 18.2,
                                "shares_sold_ipo": -1,
                                "shares_after_ipo": 25_313_314,
                            }
                        ],
                    }
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")

            filtered, removed = enforce_public_feed_policy(output)

            self.assertEqual(removed, 0)
            person = filtered["filings"][0]["people"][0]
            self.assertEqual(person["shares"], 25_313_314.0)
            self.assertEqual(person["ownership_percent"], 17.0)
            self.assertIsNone(person["ownership_percent_before"])
            self.assertEqual(person["ownership_percent_after"], 17.0)
            self.assertIsNone(person["shares_before_ipo"])
            self.assertIsNone(person["shares_sold_ipo"])
            self.assertEqual(person["shares_after_ipo"], 25_313_314)

            persisted = json.loads(output.read_text(encoding="utf-8"))
            persisted_person = persisted["filings"][0]["people"][0]
            self.assertIsNone(persisted_person["ownership_percent_before"])
            self.assertIsNone(persisted_person["shares_before_ipo"])

    def test_release_gate_clears_values_derived_from_invalid_share_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "filings": [
                    {
                        "id": "invalid-shares",
                        "company": "Example Operating Co.",
                        "form": "424B4",
                        "filed": "2026-07-16",
                        "value": 125_000_000,
                        "current_price": 10.0,
                        "people": [
                            {
                                "name": "Jane Example",
                                "shares": 18.2,
                                "cash_value": 182.0,
                                "liquid_shares": -1,
                                "liquid_value": 50.0,
                                "locked_shares": 4.5,
                                "locked_value": 45.0,
                            }
                        ],
                    }
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")

            filtered, _ = enforce_public_feed_policy(output)

            person = filtered["filings"][0]["people"][0]
            self.assertIsNone(person["shares"])
            self.assertIsNone(person.get("cash_value"))
            self.assertIsNone(person["liquid_shares"])
            self.assertIsNone(person.get("liquid_value"))
            self.assertIsNone(person["locked_shares"])
            self.assertIsNone(person.get("locked_value"))


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from public_feed_policy import enforce_public_feed_policy


class PublicFeedQuoteGateTests(unittest.TestCase):
    def test_release_gate_removes_prepricing_quote_and_derived_owner_values(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "filings": [
                    {
                        "id": "prepricing-1",
                        "company": "Acme Robotics, Inc.",
                        "ticker": "ACME",
                        "form": "S-1/A",
                        "stage": "Pre-pricing",
                        "filed": "2026-08-24",
                        "value": 45_000_000,
                        "price_range": "$18.00-$20.00",
                        "current_price": 31.25,
                        "price_updated": "2026-08-24T15:05:14+00:00",
                        "people": [
                            {
                                "name": "Jane Founder",
                                "shares": 2_000_000,
                                "cash_value": 62_500_000,
                                "liquid_value": 12_500_000,
                                "locked_value": 50_000_000,
                                "valuation_as_of": "2026-08-24",
                            }
                        ],
                    }
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")

            filtered, removed = enforce_public_feed_policy(output)

            self.assertEqual(removed, 0)
            filing = filtered["filings"][0]
            self.assertNotIn("current_price", filing)
            self.assertNotIn("price_updated", filing)
            owner = filing["people"][0]
            self.assertNotIn("cash_value", owner)
            self.assertNotIn("liquid_value", owner)
            self.assertNotIn("locked_value", owner)
            self.assertNotIn("valuation_as_of", owner)

            persisted = json.loads(output.read_text(encoding="utf-8"))["filings"][0]
            self.assertNotIn("current_price", persisted)
            self.assertNotIn("cash_value", persisted["people"][0])


if __name__ == "__main__":
    unittest.main()

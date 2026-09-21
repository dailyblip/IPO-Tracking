import json
import tempfile
import unittest
from pathlib import Path

from public_feed_policy import enforce_public_feed_policy


class CanonicalLifecycleDateGateTests(unittest.TestCase):
    def test_release_gate_clears_prepricing_pricing_date_and_persists_filing_price(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "filings": [
                    {
                        "id": "acme-prepricing",
                        "company": "Acme Robotics, Inc.",
                        "ticker": "ACME",
                        "form": "S-1/A",
                        "stage": "Pre-pricing",
                        "filed": "2026-09-01",
                        "filing_date": "2026-08-20",
                        "pricing_date": "2026-09-10",
                        "filing_price": "$18.00–$20.00",
                        "price_range": "$18.00–$20.00",
                        "value": None,
                    }
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")

            filtered, removed = enforce_public_feed_policy(output)

            self.assertEqual(removed, 0)
            self.assertEqual(len(filtered["filings"]), 1)
            row = filtered["filings"][0]
            self.assertIsNone(row["pricing_date"])
            self.assertEqual(row["filing_price"], "$18.00–$20.00")
            self.assertEqual(row["price_range"], "$18.00–$20.00")

            persisted = json.loads(output.read_text(encoding="utf-8"))["filings"][0]
            self.assertIsNone(persisted["pricing_date"])
            self.assertEqual(persisted["filing_price"], "$18.00–$20.00")
            self.assertEqual(persisted["price_range"], "$18.00–$20.00")

    def test_release_gate_preserves_valid_priced_424b4_pricing_date(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "filings": [
                    {
                        "id": "acme-priced",
                        "company": "Acme Software, Inc.",
                        "ticker": "ACME",
                        "form": "424B4",
                        "stage": "Priced",
                        "filed": "2026-09-10",
                        "filing_date": "2026-08-20",
                        "pricing_date": "2026-09-09",
                        "filing_price": "$18.00–$20.00",
                        "price_range": "$18.00–$20.00",
                        "offering_price": 20.0,
                        "value": None,
                    }
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")

            filtered, removed = enforce_public_feed_policy(output)

            self.assertEqual(removed, 0)
            row = filtered["filings"][0]
            self.assertEqual(row["pricing_date"], "2026-09-09")
            self.assertEqual(row["filing_price"], "$18.00–$20.00")
            persisted = json.loads(output.read_text(encoding="utf-8"))["filings"][0]
            self.assertEqual(persisted["pricing_date"], "2026-09-09")


if __name__ == "__main__":
    unittest.main()

import csv
import json
import tempfile
import unittest
from pathlib import Path

from public_feed_policy import enforce_public_feed_policy


class PersonSaleReleaseGateTests(unittest.TestCase):
    def test_reformation_impossible_holder_sale_is_cleared_and_csv_stays_synced(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "filings": [
                    {
                        "id": "0001104659-26-088733",
                        "company": "Reformation Inc.",
                        "ticker": "REF",
                        "cik": "0001787117",
                        "accession_no": "0001104659-26-088733",
                        "form": "424B4",
                        "filed": "2026-07-30",
                        "pricing_date": "2026-07-30",
                        "stage": "Priced",
                        "value": 210_937_500.0,
                        "primary_offering_shares": 9_478_821,
                        "secondary_offering_shares": 4_583_679,
                        "offering_price": 15.0,
                        "people": [
                            {
                                "name": "Entities affiliated with Permira",
                                "shares_sold_ipo": 32_078_948,
                                "cash_realized_ipo": 481_184_220.0,
                            },
                            {
                                "name": "Supported Selling Holder",
                                "shares_sold_ipo": 1_000_000,
                                "cash_realized_ipo": 15_000_000.0,
                            },
                        ],
                    }
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")

            filtered, removed = enforce_public_feed_policy(
                output,
                followon_submissions_loader=lambda _cik: {"filings": {"recent": {}}},
            )

            self.assertEqual(removed, 0)
            people = filtered["filings"][0]["people"]
            self.assertIsNone(people[0]["shares_sold_ipo"])
            self.assertIsNone(people[0]["cash_realized_ipo"])
            self.assertEqual(people[1]["shares_sold_ipo"], 1_000_000)
            self.assertEqual(people[1]["cash_realized_ipo"], 15_000_000.0)

            persisted = json.loads(output.read_text(encoding="utf-8"))
            persisted_people = persisted["filings"][0]["people"]
            self.assertIsNone(persisted_people[0]["shares_sold_ipo"])
            self.assertIsNone(persisted_people[0]["cash_realized_ipo"])

            with output.with_suffix(".csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            by_holder = {row["holder_name"]: row for row in rows}
            self.assertEqual(by_holder["Entities affiliated with Permira"]["shares_sold_ipo"], "")
            self.assertEqual(by_holder["Entities affiliated with Permira"]["cash_realized_ipo"], "")
            self.assertEqual(by_holder["Supported Selling Holder"]["shares_sold_ipo"], "1000000")
            self.assertEqual(by_holder["Supported Selling Holder"]["cash_realized_ipo"], "15000000.0")


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from public_feed_policy import enforce_public_feed_policy


class PersonSalePositionIntegrityTests(unittest.TestCase):
    def test_holder_sale_cannot_exceed_disclosed_pre_ipo_position(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "filings": [
                    {
                        "id": "holder-position-overflow",
                        "company": "Example Operating Co.",
                        "ticker": "EXMP",
                        "cik": "0000000001",
                        "accession_no": "0000000000-26-000003",
                        "form": "424B4",
                        "filed": "2026-08-20",
                        "pricing_date": "2026-08-20",
                        "stage": "Priced",
                        "value": 10_000.0,
                        "primary_offering_shares": 800,
                        "secondary_offering_shares": 200,
                        "offering_price": 10.0,
                        "people": [
                            {
                                "name": "Impossible Selling Holder",
                                "shares_before_ipo": 100,
                                "shares_sold_ipo": 150,
                                "shares_after_ipo": 50,
                                "cash_realized_ipo": 1_500.0,
                                "ownership_percent_before": 10.0,
                                "ownership_percent_after": 5.0,
                            },
                            {
                                "name": "Supported Selling Holder",
                                "shares_before_ipo": 300,
                                "shares_sold_ipo": 50,
                                "shares_after_ipo": 250,
                                "cash_realized_ipo": 500.0,
                                "ownership_percent_before": 30.0,
                                "ownership_percent_after": 25.0,
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

            impossible = people[0]
            self.assertEqual(impossible["shares_before_ipo"], 100)
            self.assertEqual(impossible["shares_after_ipo"], 50)
            self.assertEqual(impossible["ownership_percent_before"], 10.0)
            self.assertEqual(impossible["ownership_percent_after"], 5.0)
            self.assertIsNone(impossible["shares_sold_ipo"])
            self.assertIsNone(impossible["cash_realized_ipo"])

            supported = people[1]
            self.assertEqual(supported["shares_before_ipo"], 300)
            self.assertEqual(supported["shares_sold_ipo"], 50)
            self.assertEqual(supported["shares_after_ipo"], 250)
            self.assertEqual(supported["cash_realized_ipo"], 500.0)

            persisted = json.loads(output.read_text(encoding="utf-8"))
            persisted_people = persisted["filings"][0]["people"]
            self.assertIsNone(persisted_people[0]["shares_sold_ipo"])
            self.assertIsNone(persisted_people[0]["cash_realized_ipo"])
            self.assertEqual(persisted_people[1]["shares_sold_ipo"], 50)


if __name__ == "__main__":
    unittest.main()

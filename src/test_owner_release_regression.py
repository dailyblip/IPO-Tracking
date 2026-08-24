import json
import tempfile
import unittest
from pathlib import Path

from public_feed_policy import enforce_public_feed_policy


class OwnerReleaseRegressionTests(unittest.TestCase):
    def test_aggregate_affiliate_owner_labels_persist_as_entities(self):
        labels = (
            "Entities affiliated with Westlake BioPartners",
            "Funds affiliated with Example Ventures",
            "Affiliated entities of Example Capital",
            "Affiliates of Example Partners",
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "filings": [
                    {
                        "id": "owner-release-regression",
                        "company": "Qualifying Operating Company, Inc.",
                        "form": "424B4",
                        "filed": "2026-08-24",
                        "value": 150_000_000,
                        "people": [
                            {"name": label, "holder_type": "Individual"}
                            for label in labels
                        ],
                    }
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")

            enforce_public_feed_policy(output)

            persisted = json.loads(output.read_text(encoding="utf-8"))
            people = persisted["filings"][0]["people"]
            self.assertEqual([person["holder_type"] for person in people], ["Entity"] * len(labels))


if __name__ == "__main__":
    unittest.main()

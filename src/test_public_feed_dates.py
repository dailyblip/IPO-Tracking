import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from public_feed_policy import enforce_public_feed_policy


class PublicFeedDatePolicyTests(unittest.TestCase):
    def _record(self, filing_id, filed):
        return {
            "id": filing_id,
            "company": f"{filing_id} Operating Co",
            "form": "424B4",
            "filed": filed,
            "value": 150_000_000,
            "people": [],
        }

    def test_release_requires_canonical_non_future_filing_date(self):
        today = date.today()
        valid = (today - timedelta(days=1)).isoformat()
        future = (today + timedelta(days=1)).isoformat()

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "filings": [
                    self._record("valid", valid),
                    self._record("missing", None),
                    self._record("blank", ""),
                    self._record("malformed", "2026-02-30"),
                    self._record("noncanonical", "2026-8-07"),
                    self._record("future", future),
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")

            filtered, removed = enforce_public_feed_policy(output)

            self.assertEqual(removed, 5)
            self.assertEqual([row["id"] for row in filtered["filings"]], ["valid"])

            persisted = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual([row["id"] for row in persisted["filings"]], ["valid"])

            csv_text = output.with_suffix(".csv").read_text(encoding="utf-8")
            self.assertIn("valid Operating Co", csv_text)
            for excluded in ("missing", "blank", "malformed", "noncanonical", "future"):
                self.assertNotIn(f"{excluded} Operating Co", csv_text)


if __name__ == "__main__":
    unittest.main()

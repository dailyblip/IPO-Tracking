import json
import tempfile
import unittest
from pathlib import Path

from public_feed_policy import enforce_public_feed_policy


def _submissions(forms, dates):
    return {
        "filings": {
            "recent": {
                "form": forms,
                "filingDate": dates,
            }
        }
    }


class PublicFollowOnReleaseGateTests(unittest.TestCase):
    def test_canonical_release_gate_removes_post_reporting_424b4(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "generated_at": "2026-08-27T00:00:00+00:00",
                "source": "SEC EDGAR",
                "filings": [
                    {
                        "id": "initial-ipo",
                        "company": "Initial IPO, Inc.",
                        "ticker": "INIT",
                        "cik": "1000001",
                        "form": "424B4",
                        "filed": "2026-08-20",
                        "pricing_date": "2026-08-20",
                        "stage": "Priced",
                        "value": None,
                        "people": [],
                    },
                    {
                        "id": "follow-on",
                        "company": "Already Public, Inc.",
                        "ticker": "PUBC",
                        "cik": "1000002",
                        "form": "424B4",
                        "filed": "2026-08-20",
                        "pricing_date": "2026-08-20",
                        "stage": "Priced",
                        "value": None,
                        "people": [],
                    },
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")

            def loader(cik):
                if cik == "1000002":
                    return _submissions(
                        ["424B4", "10-Q", "S-1"],
                        ["2026-08-20", "2026-05-10", "2025-12-01"],
                    )
                return _submissions(
                    ["424B4", "S-1"],
                    ["2026-08-20", "2026-08-01"],
                )

            filtered, removed = enforce_public_feed_policy(
                output,
                followon_submissions_loader=loader,
            )

            self.assertEqual(removed, 1)
            self.assertEqual(
                [filing["id"] for filing in filtered["filings"]],
                ["initial-ipo"],
            )
            persisted = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                [filing["id"] for filing in persisted["filings"]],
                ["initial-ipo"],
            )
            csv_text = output.with_suffix(".csv").read_text(encoding="utf-8")
            self.assertIn("Initial IPO", csv_text)
            self.assertNotIn("Already Public", csv_text)


if __name__ == "__main__":
    unittest.main()

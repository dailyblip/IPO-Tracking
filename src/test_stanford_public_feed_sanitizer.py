import json
import tempfile
import unittest
from pathlib import Path

from public_feed_policy import enforce_public_feed_policy


class StanfordPublicFeedSanitizerTests(unittest.TestCase):
    def test_release_policy_removes_internal_notes_but_preserves_confirmed_evidence(self):
        confirmed = (
            "Confidence 5/5 — SEC 424B4 management biography confirms a degree "
            "from Stanford University. Source: https://www.sec.gov/example"
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filings.json"
            payload = {
                "schema_version": 1,
                "filings": [
                    {
                        "id": "acme",
                        "company": "Acme Robotics, Inc.",
                        "form": "424B4",
                        "filed": "2026-08-24",
                        "value": 250_000_000,
                        "people": [
                            {
                                "name": "Jane Researcher",
                                "holder_type": "Individual",
                                "stanford_university_bio": False,
                                "stanford_source": (
                                    "Grading failed to run: OpenAI Stanford research request "
                                    "failed (429): insufficient_quota; no credits remaining"
                                ),
                            },
                            {
                                "name": "Entities affiliated with Example Ventures",
                                "holder_type": "Entity",
                                "stanford_university_bio": False,
                                "stanford_source": (
                                    "Beneficial-owner label appears to be an organization or combined "
                                    "affiliate row; person-level Stanford grading skipped."
                                ),
                            },
                            {
                                "name": "John Alum",
                                "holder_type": "Individual",
                                "shares": 100_000,
                                "stanford_university_bio": True,
                                "stanford_source": confirmed,
                            },
                        ],
                    }
                ],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")

            filtered, removed = enforce_public_feed_policy(output)

            self.assertEqual(removed, 0)
            people = filtered["filings"][0]["people"]
            self.assertEqual(people[0]["stanford_source"], "")
            self.assertFalse(people[0]["stanford_university_bio"])
            self.assertEqual(people[1]["stanford_source"], "")
            self.assertFalse(people[1]["stanford_university_bio"])
            self.assertEqual(people[2]["stanford_source"], confirmed)
            self.assertTrue(people[2]["stanford_university_bio"])

            persisted = json.loads(output.read_text(encoding="utf-8"))
            text = json.dumps(persisted).casefold()
            self.assertNotIn("insufficient_quota", text)
            self.assertNotIn("no credits remaining", text)
            self.assertNotIn("person-level stanford grading skipped", text)
            self.assertIn("confidence 5/5", text)


if __name__ == "__main__":
    unittest.main()

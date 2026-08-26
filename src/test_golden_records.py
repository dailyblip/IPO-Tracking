import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "docs" / "data" / "filings.json"
FIXTURE_PATH = ROOT / "tests" / "golden_records.json"


class GoldenRecordRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feed = json.loads(FEED_PATH.read_text(encoding="utf-8"))
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.by_cik = {
            str(filing.get("cik") or "").strip(): filing
            for filing in cls.feed.get("filings", [])
            if str(filing.get("cik") or "").strip()
        }

    def test_golden_records_match_live_feed(self):
        self.assertEqual(self.fixture.get("schema_version"), 1)
        records = self.fixture.get("records")
        self.assertIsInstance(records, list)
        self.assertGreaterEqual(len(records), 5)

        failures = []
        for golden in records:
            cik = golden["cik"]
            label = golden.get("label") or cik
            actual = self.by_cik.get(cik)
            if actual is None:
                failures.append(f"{label} [{cik}]: record missing from public feed")
                continue

            for field, expected in golden.get("expected", {}).items():
                observed = actual.get(field)
                if observed != expected:
                    failures.append(
                        f"{label} [{cik}]: {field} drifted; expected {expected!r}, got {observed!r}"
                    )

            people = {
                str(person.get("name") or "").strip(): person
                for person in actual.get("people", [])
                if str(person.get("name") or "").strip()
            }
            for required_person in golden.get("required_people", []):
                name = required_person["name"]
                person = people.get(name)
                if person is None:
                    failures.append(f"{label} [{cik}]: required person {name!r} is missing")
                    continue

                for field, expected in required_person.get("expected", {}).items():
                    observed = person.get(field)
                    if observed != expected:
                        failures.append(
                            f"{label} [{cik}] / {name}: {field} drifted; "
                            f"expected {expected!r}, got {observed!r}"
                        )

                source_fragment = required_person.get("stanford_source_contains")
                if source_fragment:
                    source = str(person.get("stanford_source") or "")
                    if source_fragment not in source:
                        failures.append(
                            f"{label} [{cik}] / {name}: Stanford provenance drifted; "
                            f"expected source containing {source_fragment!r}, got {source!r}"
                        )

        if failures:
            self.fail("Golden-record regression failure:\n- " + "\n- ".join(failures))


if __name__ == "__main__":
    unittest.main()

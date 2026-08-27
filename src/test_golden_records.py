import json
import re
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

    def test_public_feed_invariants(self):
        filings = self.feed.get("filings", [])
        ciks = [str(filing.get("cik") or "").strip() for filing in filings]
        self.assertEqual(len(ciks), len(set(ciks)), "duplicate CIKs leaked into the public feed")

        company_keys = [
            re.sub(r"[^a-z0-9]+", "", str(filing.get("company") or "").casefold())
            for filing in filings
        ]
        self.assertTrue(all(company_keys), "blank company name leaked into the public feed")
        self.assertEqual(
            len(company_keys), len(set(company_keys)),
            "duplicate normalized company names leaked into the public feed",
        )

        spac_name = re.compile(
            r"\b(?:blank check|special purpose acquisition|SPAC)\b|"
            r"\b(?:Acquisition|Capital)\s+(?:Corp(?:oration)?|Company)\b",
            re.IGNORECASE,
        )
        for filing in filings:
            company = str(filing.get("company") or "")
            self.assertNotRegex(company, spac_name, f"SPAC-like issuer leaked into feed: {company}")
            self.assertIn(filing.get("stage"), {"Pre-pricing", "Priced"})
            signals = filing.get("signals")
            self.assertIsInstance(signals, list, f"{company}: signals must remain a list")
            self.assertTrue(all(isinstance(signal, str) and signal.strip() for signal in signals))
            self.assertEqual(len(signals), len(set(signals)), f"{company}: duplicate signals")

            people = filing.get("people") or []
            person_keys = [
                re.sub(r"[^a-z0-9]+", "", re.sub(r"\.{3,}", "", str(person.get("name") or "")).casefold())
                for person in people
            ]
            self.assertTrue(all(person_keys), f"{company}: blank owner identity")
            self.assertEqual(
                len(person_keys), len(set(person_keys)),
                f"{company}: duplicate normalized owner identity",
            )

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

            for field in golden.get("expected_null_fields", []):
                if actual.get(field) is not None:
                    failures.append(
                        f"{label} [{cik}]: {field} should remain null; got {actual.get(field)!r}"
                    )

            for fragment in golden.get("expected_signals_contain", []):
                signals = actual.get("signals") or []
                if not any(fragment in str(signal) for signal in signals):
                    failures.append(
                        f"{label} [{cik}]: expected signal containing {fragment!r}; got {signals!r}"
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

                source_fragments = required_person.get("stanford_source_contains", [])
                if isinstance(source_fragments, str):
                    source_fragments = [source_fragments]
                for source_fragment in source_fragments:
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

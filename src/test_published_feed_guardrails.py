import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "docs" / "data" / "filings.json"


class PublishedFeedGuardrailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feed = json.loads(FEED_PATH.read_text(encoding="utf-8"))
        cls.filings = cls.feed.get("filings", [])

    def test_published_feed_has_no_obvious_non_operating_investment_products(self):
        forbidden = re.compile(
            r"\b(?:ETF|ETN|exchange[- ]traded fund|exchange[- ]traded note|"
            r"closed[- ]end fund|interval fund|mutual fund|unit investment trust|"
            r"commodity pool|pooled investment vehicle|grantor trust)\b",
            re.IGNORECASE,
        )
        for filing in self.filings:
            company = str(filing.get("company") or "")
            with self.subTest(company=company):
                self.assertIsNone(
                    forbidden.search(company),
                    f"Non-operating investment product leaked into public feed: {company}",
                )

    def test_confirmed_stanford_beneficial_owners_have_public_evidence(self):
        for filing in self.filings:
            for person in filing.get("people", []):
                shares = person.get("shares")
                confirmed_owner = (
                    person.get("stanford_university_bio") is True
                    and isinstance(shares, (int, float))
                    and shares > 0
                )
                if not confirmed_owner:
                    continue
                with self.subTest(company=filing.get("company"), person=person.get("name")):
                    self.assertTrue(str(person.get("name") or "").strip())
                    self.assertTrue(
                        str(person.get("stanford_source") or "").strip(),
                        "Confirmed Stanford beneficial-owner highlighting requires public source evidence.",
                    )

    def test_public_rows_have_core_identity_fields(self):
        for filing in self.filings:
            with self.subTest(company=filing.get("company")):
                for field in ("company", "form", "stage", "filed"):
                    self.assertTrue(
                        str(filing.get(field) or "").strip(),
                        f"Published IPO row is missing required identity field: {field}",
                    )


if __name__ == "__main__":
    unittest.main()

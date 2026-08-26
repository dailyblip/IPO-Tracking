import json
import unittest
from pathlib import Path

from edgar_client import INVESTMENT_PRODUCT_NAME_PATTERN, SPAC_NAME_PATTERN


ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "docs" / "data" / "filings.json"


class PublishedFeedIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feed = json.loads(FEED_PATH.read_text(encoding="utf-8"))
        cls.filings = cls.feed.get("filings", [])

    def test_no_excluded_issuer_name_patterns_survive_public_feed(self):
        for filing in self.filings:
            company = str(filing.get("company") or "").strip()
            with self.subTest(company=company):
                self.assertFalse(
                    SPAC_NAME_PATTERN.search(company),
                    f"SPAC-like issuer leaked into public feed: {company}",
                )
                self.assertFalse(
                    INVESTMENT_PRODUCT_NAME_PATTERN.search(company),
                    f"Investment product leaked into public feed: {company}",
                )

    def test_confirmed_stanford_beneficial_owners_have_public_evidence(self):
        confirmed = []
        for filing in self.filings:
            for person in filing.get("people", []):
                shares = person.get("shares")
                if person.get("stanford_university_bio") is True and isinstance(shares, (int, float)) and shares > 0:
                    confirmed.append((filing, person))

        self.assertTrue(
            confirmed,
            "Published feed must retain at least one confirmed Stanford-affiliated beneficial owner.",
        )

        for filing, person in confirmed:
            label = f"{filing.get('company')} / {person.get('name')}"
            with self.subTest(owner=label):
                self.assertTrue(str(person.get("name") or "").strip())
                self.assertGreater(person["shares"], 0)
                self.assertTrue(
                    str(person.get("stanford_source") or "").strip(),
                    f"Confirmed Stanford owner lacks public source evidence: {label}",
                )

    def test_stanford_flag_does_not_highlight_non_beneficial_rows(self):
        for filing in self.filings:
            for person in filing.get("people", []):
                if person.get("stanford_university_bio") is not True:
                    continue
                shares = person.get("shares")
                with self.subTest(company=filing.get("company"), owner=person.get("name")):
                    self.assertIsInstance(
                        shares,
                        (int, float),
                        "Confirmed Stanford rows must have an explicit beneficial share count before highlighting.",
                    )
                    self.assertGreater(
                        shares,
                        0,
                        "Confirmed Stanford rows must represent a positive beneficial holding before highlighting.",
                    )


if __name__ == "__main__":
    unittest.main()

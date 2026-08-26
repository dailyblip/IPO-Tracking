import json
import unittest
from pathlib import Path

from edgar_client import INVESTMENT_PRODUCT_NAME_PATTERN, SPAC_NAME_PATTERN


ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "docs" / "data" / "filings.json"
DASHBOARD_PATH = ROOT / "docs" / "index.html"


class PublishedFeedIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feed = json.loads(FEED_PATH.read_text(encoding="utf-8"))
        cls.filings = cls.feed.get("filings", [])
        cls.dashboard = DASHBOARD_PATH.read_text(encoding="utf-8")

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

    def test_stanford_highlight_requires_confirmed_positive_beneficial_holding(self):
        """Affiliation research may cover management; red text must remain owner-only."""
        self.assertIn(
            "function isStanfordBeneficialOwner(person){const shares=Number(person.shares);return person.stanford_university_bio===true&&Number.isFinite(shares)&&shares>0}",
            self.dashboard,
            "Dashboard Stanford highlighting must require confirmed affiliation and a positive disclosed holding.",
        )
        self.assertIn(
            "hasStanfordBeneficialOwner(filing)?\"company stanford-company\":\"company\"",
            self.dashboard,
            "Company Cardinal-red styling must be driven only by a qualifying Stanford beneficial owner.",
        )

        for filing in self.filings:
            for person in filing.get("people", []):
                if person.get("stanford_university_bio") is not True:
                    continue
                shares = person.get("shares")
                if isinstance(shares, (int, float)) and shares > 0:
                    continue
                with self.subTest(company=filing.get("company"), person=person.get("name")):
                    self.assertFalse(
                        isinstance(person.get("cash_value"), (int, float)) and person.get("cash_value") > 0,
                        "A Stanford-confirmed management-only row must not fabricate a holding value.",
                    )


if __name__ == "__main__":
    unittest.main()

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

    def test_priced_filing_prices_have_authoritative_sec_provenance(self):
        """A published preliminary price must retain its authoritative S-1 history."""
        checked = 0
        failures = []
        for filing in self.filings:
            if str(filing.get("stage") or "").casefold() != "priced":
                continue
            filing_price = str(filing.get("filing_price") or "").strip()
            if not filing_price:
                continue

            checked += 1
            label = filing.get("company") or filing.get("id") or "unknown filing"
            source = filing.get("filing_price_source")
            if not isinstance(source, dict):
                failures.append(f"{label}: Filing Price lacks source provenance")
                continue
            if str(source.get("source") or "").strip() != "SEC EDGAR":
                failures.append(f"{label}: Filing Price source is not SEC EDGAR")
            if str(source.get("form") or "").strip() not in {"S-1", "S-1/A"}:
                failures.append(f"{label}: Filing Price source is not S-1/S-1A")
            for field in ("filing_date", "accession_no", "sec_url"):
                if not str(source.get(field) or "").strip():
                    failures.append(f"{label}: Filing Price provenance lacks {field}")
            sec_url = str(source.get("sec_url") or "").strip()
            if sec_url and not sec_url.startswith("https://www.sec.gov/"):
                failures.append(f"{label}: Filing Price provenance is not an SEC URL")

        self.assertGreater(checked, 0, "No priced IPO has a Filing Price to validate")
        self.assertEqual(
            failures,
            [],
            "Published Filing Price provenance failures: " + "; ".join(failures[:10]),
        )


if __name__ == "__main__":
    unittest.main()

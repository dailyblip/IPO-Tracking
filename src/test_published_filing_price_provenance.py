import json
import re
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "docs" / "data" / "filings.json"


def _display(value):
    if value in (None, "", "Unknown", "—", "-"):
        return ""
    return str(value).strip()


def _iso_date(value):
    text = _display(value)
    if not text:
        return None
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == text else None


def _digits(value):
    return re.sub(r"\D", "", _display(value))


class PublishedFilingPriceProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feed = json.loads(FEED_PATH.read_text(encoding="utf-8"))
        cls.records = cls.feed["filings"] if isinstance(cls.feed, dict) else cls.feed

    def test_priced_filing_price_provenance_matches_registration_identity(self):
        failures = []
        checked = 0
        for record in self.records:
            if _display(record.get("stage")) != "Priced":
                continue
            filing_price = _display(record.get("filing_price"))
            price_range = _display(record.get("price_range"))
            preliminary = filing_price or price_range
            if not preliminary:
                continue

            checked += 1
            label = _display(
                record.get("company")
                or record.get("issuer_name")
                or record.get("name")
                or record.get("cik")
            ) or "unknown issuer"

            if filing_price and price_range and filing_price != price_range:
                failures.append(f"{label}: filing_price and price_range aliases disagree")

            source = record.get("filing_price_source")
            if not isinstance(source, dict):
                failures.append(f"{label}: populated Filing Price lacks filing_price_source")
                continue

            if _display(source.get("form")).upper() not in {"S-1", "S-1/A"}:
                failures.append(f"{label}: Filing Price source form is not S-1/S-1/A")

            source_date = _iso_date(source.get("filing_date"))
            initial_date = _iso_date(record.get("filing_date"))
            pricing_date = _iso_date(record.get("pricing_date"))

            if source_date is None:
                failures.append(f"{label}: Filing Price source has invalid filing_date")
            else:
                if initial_date is not None and source_date < initial_date:
                    failures.append(f"{label}: Filing Price source predates current registration")
                if pricing_date is not None and source_date > pricing_date:
                    failures.append(f"{label}: Filing Price source postdates pricing")

            sec_url = _display(source.get("sec_url"))
            parsed = urlparse(sec_url)
            if (
                parsed.scheme != "https"
                or parsed.hostname not in {"www.sec.gov", "sec.gov"}
                or "/Archives/edgar/data/" not in parsed.path
            ):
                failures.append(f"{label}: Filing Price source is not an SEC Archives URL")
                continue

            cik_digits = _digits(record.get("cik"))
            if not cik_digits:
                failures.append(f"{label}: cannot verify Filing Price source without CIK")
            else:
                expected_cik_path = f"/Archives/edgar/data/{int(cik_digits)}/"
                if expected_cik_path not in parsed.path:
                    failures.append(f"{label}: Filing Price source URL points to another CIK")

            accession_digits = _digits(source.get("accession_no"))
            if not accession_digits:
                failures.append(f"{label}: Filing Price source accession is missing")
            elif accession_digits not in _digits(parsed.path):
                failures.append(f"{label}: Filing Price source URL does not match source accession")

        self.assertGreater(
            checked,
            0,
            "expected at least one priced row with a preliminary Filing Price",
        )
        self.assertFalse(failures, "\n".join(failures))


if __name__ == "__main__":
    unittest.main()

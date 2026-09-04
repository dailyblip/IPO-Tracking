import json
import re
import unittest
from datetime import date
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"
ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SEC_ARCHIVES_PREFIX = "https://www.sec.gov/Archives/edgar/data/"
SEC_ARCHIVES_CIK_PATTERN = re.compile(r"/Archives/edgar/data/(\d+)/", re.IGNORECASE)


def _normalize_cik(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else None


def _canonical_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def _filing_price_source_failures(filing):
    preliminary = str(filing.get("filing_price") or filing.get("price_range") or "").strip()
    if not preliminary:
        return []

    source = filing.get("filing_price_source")
    if not isinstance(source, dict):
        return ["populated Filing Price lacks SEC provenance"]

    accession = str(source.get("accession_no") or "").strip()
    sec_url = str(source.get("sec_url") or "").strip()
    row_cik = _normalize_cik(filing.get("cik"))
    sec_cik_match = SEC_ARCHIVES_CIK_PATTERN.search(sec_url)
    sec_url_cik = int(sec_cik_match.group(1)) if sec_cik_match else None
    source_date = _canonical_date(source.get("filing_date"))
    pricing_date = _canonical_date(filing.get("pricing_date"))

    failures = []
    if str(source.get("source") or "").strip().casefold() != "sec edgar":
        failures.append("Filing Price source is not SEC EDGAR")
    if str(source.get("form") or "").strip().upper() not in {"S-1", "S-1/A"}:
        failures.append("Filing Price source is not S-1/S-1A")
    if not ACCESSION_PATTERN.fullmatch(accession):
        failures.append(f"Filing Price source lacks a canonical SEC accession number: {accession!r}")
    if source_date is None:
        failures.append("Filing Price source lacks a valid SEC filing date")
    if str(filing.get("pricing_date") or "").strip() and pricing_date is None:
        failures.append("priced row has an invalid Pricing Date for Filing Price chronology")
    if source_date is not None and pricing_date is not None and source_date > pricing_date:
        failures.append(
            f"Filing Price source date {source_date.isoformat()} postdates Pricing Date "
            f"{pricing_date.isoformat()}"
        )

    if not sec_url.startswith(SEC_ARCHIVES_PREFIX):
        failures.append("Filing Price source does not link to an SEC Archives filing")
    else:
        if sec_url_cik is None:
            failures.append("Filing Price SEC URL does not encode an issuer CIK")
        elif row_cik is None:
            failures.append("priced row lacks a valid issuer CIK for Filing Price provenance matching")
        elif sec_url_cik != row_cik:
            failures.append(
                f"Filing Price SEC URL issuer CIK {sec_url_cik} does not match row CIK {row_cik}"
            )

        if accession and accession.replace("-", "") not in sec_url.replace("-", ""):
            failures.append(f"Filing Price SEC URL does not match accession {accession}")

    return failures


class FilingPriceSECProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        cls.filings = payload.get("filings", []) if isinstance(payload, dict) else payload

    def test_published_filing_prices_are_anchored_to_same_issuer_sec_history(self):
        """A preserved preliminary range must remain tied to this issuer's preceding S-1/S-1A."""
        failures = []
        checked = 0

        for filing in self.filings:
            form = str(filing.get("form") or "").strip().upper()
            stage = str(filing.get("stage") or "").strip().casefold()
            preliminary = str(filing.get("filing_price") or filing.get("price_range") or "").strip()
            if form != "424B4" or stage != "priced" or not preliminary:
                continue

            checked += 1
            label = filing.get("company") or filing.get("id") or "unknown filing"
            failures.extend(
                f"{label}: {reason}" for reason in _filing_price_source_failures(filing)
            )

        self.assertGreater(checked, 0, "No priced rows with Filing Price were available to validate")
        self.assertEqual(
            failures,
            [],
            "Filing Price SEC provenance failures: " + "; ".join(failures[:10]),
        )

    def test_cross_issuer_filing_price_source_is_rejected_even_when_accession_matches(self):
        accession = "0001234567-26-000001"
        filing = {
            "cik": "0001234567",
            "filing_price": "14-16",
            "filing_price_source": {
                "source": "SEC EDGAR",
                "form": "S-1/A",
                "filing_date": "2026-08-18",
                "accession_no": accession,
                "sec_url": (
                    "https://www.sec.gov/Archives/edgar/data/7654321/"
                    "000123456726000001/example-s1a.htm"
                ),
            },
        }

        failures = _filing_price_source_failures(filing)
        self.assertTrue(
            any("does not match row CIK" in reason for reason in failures),
            f"expected issuer-CIK mismatch failure, got: {failures}",
        )

    def test_wrong_accession_url_is_rejected(self):
        filing = {
            "cik": "0001234567",
            "filing_price": "14-16",
            "filing_price_source": {
                "source": "SEC EDGAR",
                "form": "S-1/A",
                "filing_date": "2026-08-18",
                "accession_no": "0001234567-26-000001",
                "sec_url": (
                    "https://www.sec.gov/Archives/edgar/data/1234567/"
                    "000123456726000999/example-s1a.htm"
                ),
            },
        }

        failures = _filing_price_source_failures(filing)
        self.assertTrue(
            any("does not match accession" in reason for reason in failures),
            f"expected accession mismatch failure, got: {failures}",
        )

    def test_post_pricing_s1_source_is_rejected(self):
        accession = "0001234567-26-000002"
        filing = {
            "cik": "0001234567",
            "form": "424B4",
            "stage": "Priced",
            "pricing_date": "2026-08-18",
            "filing_price": "14-16",
            "filing_price_source": {
                "source": "SEC EDGAR",
                "form": "S-1/A",
                "filing_date": "2026-08-19",
                "accession_no": accession,
                "sec_url": (
                    "https://www.sec.gov/Archives/edgar/data/1234567/"
                    "000123456726000002/example-s1a.htm"
                ),
            },
        }

        failures = _filing_price_source_failures(filing)
        self.assertTrue(
            any("postdates Pricing Date" in reason for reason in failures),
            f"expected post-pricing Filing Price provenance failure, got: {failures}",
        )

    def test_invalid_source_filing_date_is_rejected(self):
        accession = "0001234567-26-000003"
        filing = {
            "cik": "0001234567",
            "form": "424B4",
            "stage": "Priced",
            "pricing_date": "2026-08-18",
            "filing_price": "14-16",
            "filing_price_source": {
                "source": "SEC EDGAR",
                "form": "S-1/A",
                "filing_date": "08/17/2026",
                "accession_no": accession,
                "sec_url": (
                    "https://www.sec.gov/Archives/edgar/data/1234567/"
                    "000123456726000003/example-s1a.htm"
                ),
            },
        }

        failures = _filing_price_source_failures(filing)
        self.assertIn("Filing Price source lacks a valid SEC filing date", failures)


if __name__ == "__main__":
    unittest.main()

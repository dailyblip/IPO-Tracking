import json
import re
import unittest
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"
ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SEC_ARCHIVES_PREFIX = "https://www.sec.gov/Archives/edgar/data/"
SEC_ARCHIVES_CIK_PATTERN = re.compile(r"/Archives/edgar/data/(\d+)/", re.IGNORECASE)


def _normalize_cik(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else None


def _final_price_provenance_failures(filing):
    accession = str(filing.get("accession_no") or "").strip()
    sec_url = str(filing.get("sec_url") or "").strip()
    offering_price = filing.get("offering_price")
    row_cik = _normalize_cik(filing.get("cik"))
    sec_cik_match = SEC_ARCHIVES_CIK_PATTERN.search(sec_url)
    sec_url_cik = int(sec_cik_match.group(1)) if sec_cik_match else None

    failures = []
    if not isinstance(offering_price, (int, float)) or offering_price <= 0:
        failures.append("priced 424B4 lacks a positive Final IPO Price")

    if not ACCESSION_PATTERN.fullmatch(accession):
        failures.append(f"priced 424B4 lacks a canonical SEC accession number: {accession!r}")

    if not sec_url.startswith(SEC_ARCHIVES_PREFIX):
        failures.append("priced 424B4 does not link to an SEC Archives filing")
    else:
        if sec_url_cik is None:
            failures.append("priced-row SEC URL does not encode an issuer CIK")
        elif row_cik is None:
            failures.append("priced 424B4 lacks a valid issuer CIK for SEC provenance matching")
        elif sec_url_cik != row_cik:
            failures.append(
                f"priced-row SEC URL issuer CIK {sec_url_cik} does not match row CIK {row_cik}"
            )

        if accession and accession.replace("-", "") not in sec_url.replace("-", ""):
            failures.append(f"priced-row SEC URL does not match accession {accession}")

    return failures


class FinalIPOPriceSECProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        cls.filings = payload.get("filings", []) if isinstance(payload, dict) else payload

    def test_priced_final_prices_are_anchored_to_their_sec_424b4(self):
        """A published Final IPO Price must remain tied to its authoritative 424B4 filing."""
        failures = []
        checked = 0

        for filing in self.filings:
            form = str(filing.get("form") or "").strip().upper()
            stage = str(filing.get("stage") or "").strip().casefold()
            if form != "424B4" or stage != "priced":
                continue

            checked += 1
            label = filing.get("company") or filing.get("id") or "unknown filing"
            failures.extend(
                f"{label}: {reason}" for reason in _final_price_provenance_failures(filing)
            )

        self.assertGreater(checked, 0, "No priced 424B4 rows were available to validate")
        self.assertEqual(
            failures,
            [],
            "Final IPO Price SEC provenance failures: " + "; ".join(failures[:10]),
        )

    def test_cross_issuer_sec_url_is_rejected_even_when_accession_matches(self):
        """A stale SEC URL from another issuer must not substantiate a priced record."""
        accession = "0001234567-26-000001"
        filing = {
            "cik": "0001234567",
            "accession_no": accession,
            "offering_price": 25.0,
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/7654321/"
                "000123456726000001/example-424b4.htm"
            ),
        }

        failures = _final_price_provenance_failures(filing)
        self.assertTrue(
            any("does not match row CIK" in reason for reason in failures),
            f"expected issuer-CIK mismatch failure, got: {failures}",
        )


if __name__ == "__main__":
    unittest.main()

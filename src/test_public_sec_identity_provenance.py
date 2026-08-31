import json
import re
import unittest
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"
CIK_PATTERN = re.compile(r"^\d{10}$")
ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SEC_ARCHIVES_PREFIX = "https://www.sec.gov/Archives/edgar/data/"
SEC_ARCHIVES_CIK_PATTERN = re.compile(r"/Archives/edgar/data/(\d+)/", re.IGNORECASE)


def _normalize_cik(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else None


def _sec_identity_failures(filing):
    cik = str(filing.get("cik") or "").strip()
    accession = str(filing.get("accession_no") or "").strip()
    sec_url = str(filing.get("sec_url") or "").strip()
    failures = []

    if not CIK_PATTERN.fullmatch(cik):
        failures.append(f"missing or non-canonical 10-digit issuer CIK: {cik!r}")

    if not ACCESSION_PATTERN.fullmatch(accession):
        failures.append(f"missing or non-canonical SEC accession number: {accession!r}")

    if not sec_url.startswith(SEC_ARCHIVES_PREFIX):
        failures.append("SEC URL is missing or does not point to SEC Archives")
        return failures

    url_cik_match = SEC_ARCHIVES_CIK_PATTERN.search(sec_url)
    url_cik = int(url_cik_match.group(1)) if url_cik_match else None
    row_cik = _normalize_cik(cik)
    if url_cik is None:
        failures.append("SEC Archives URL does not encode an issuer CIK")
    elif row_cik is None:
        failures.append("row lacks a valid issuer CIK for SEC URL matching")
    elif url_cik != row_cik:
        failures.append(f"SEC URL issuer CIK {url_cik} does not match row CIK {row_cik}")

    if accession and accession.replace("-", "") not in sec_url.replace("-", ""):
        failures.append(f"SEC URL does not match row accession {accession}")

    return failures


class PublicSECIdentityProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        cls.filings = payload.get("filings", []) if isinstance(payload, dict) else payload

    def test_every_public_row_is_anchored_to_its_sec_issuer_and_accession(self):
        """Every public lifecycle row must retain canonical SEC issuer provenance.

        This protects both pre-pricing S-1/S-1A rows and priced 424B4 rows. A missing
        CIK/accession, stale cross-issuer SEC URL, or URL from a different accession
        is release-blocking because those defects can defeat lifecycle/entity matching
        even when the visible company name and ticker look plausible.
        """
        failures = []
        for filing in self.filings:
            label = filing.get("company") or filing.get("id") or "unknown filing"
            failures.extend(
                f"{label}: {reason}" for reason in _sec_identity_failures(filing)
            )

        self.assertGreater(len(self.filings), 0, "Public feed is empty")
        self.assertEqual(
            failures,
            [],
            "Public SEC identity/provenance failures: " + "; ".join(failures[:10]),
        )

    def test_cross_issuer_or_stale_accession_urls_are_rejected(self):
        accession = "0001234567-26-000001"
        cross_issuer = {
            "cik": "0001234567",
            "accession_no": accession,
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/7654321/"
                "000123456726000001/example.htm"
            ),
        }
        stale_accession = {
            "cik": "0001234567",
            "accession_no": accession,
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/1234567/"
                "000765432126000999/0007654321-26-000999-index.htm"
            ),
        }

        cross_failures = _sec_identity_failures(cross_issuer)
        stale_failures = _sec_identity_failures(stale_accession)
        self.assertTrue(any("does not match row CIK" in item for item in cross_failures))
        self.assertTrue(any("does not match row accession" in item for item in stale_failures))


if __name__ == "__main__":
    unittest.main()

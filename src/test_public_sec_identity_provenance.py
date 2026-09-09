import json
import re
import unittest
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"
CIK_PATTERN = re.compile(r"^\d{10}$")
ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SEC_ARCHIVES_FILING_PATTERN = re.compile(
    r"^https://www\.sec\.gov/Archives/edgar/data/(\d+)/(\d{18})/[^/?#]+$",
    re.IGNORECASE,
)


def _normalize_cik(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else None


def _canonical_accession(value):
    accession = str(value or "").strip()
    if not ACCESSION_PATTERN.fullmatch(accession):
        return ""
    return accession.replace("-", "")


def _sec_identity_failures(filing):
    cik = str(filing.get("cik") or "").strip()
    accession = str(filing.get("accession_no") or "").strip()
    sec_url = str(filing.get("sec_url") or "").strip()
    failures = []

    if not CIK_PATTERN.fullmatch(cik):
        failures.append(f"missing or non-canonical 10-digit issuer CIK: {cik!r}")

    canonical_accession = _canonical_accession(accession)
    if not canonical_accession:
        failures.append(f"missing or non-canonical SEC accession number: {accession!r}")

    if not sec_url:
        failures.append("SEC URL is missing")
        return failures

    match = SEC_ARCHIVES_FILING_PATTERN.fullmatch(sec_url)
    if not match:
        failures.append("SEC URL is not a canonical SEC Archives filing URL")
        return failures

    url_cik_digits, url_accession = match.groups()
    url_cik = int(url_cik_digits)
    row_cik = _normalize_cik(cik)
    if row_cik is None:
        failures.append("row lacks a valid issuer CIK for SEC URL matching")
    elif url_cik != row_cik:
        failures.append(f"SEC URL issuer CIK {url_cik} does not match row CIK {row_cik}")

    if canonical_accession and url_accession != canonical_accession:
        failures.append(f"SEC URL accession directory does not match row accession {accession}")

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

    def test_canonical_sec_archives_url_is_accepted(self):
        filing = {
            "cik": "0001234567",
            "accession_no": "0001234567-26-012345",
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/1234567/"
                "000123456726012345/example-s1.htm"
            ),
        }
        self.assertEqual(_sec_identity_failures(filing), [])

    def test_cross_issuer_url_is_rejected(self):
        filing = {
            "cik": "0001234567",
            "accession_no": "0001234567-26-012345",
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/7654321/"
                "000123456726012345/example-s1.htm"
            ),
        }
        failures = _sec_identity_failures(filing)
        self.assertTrue(any("does not match row CIK" in item for item in failures))

    def test_wrong_accession_directory_is_rejected(self):
        filing = {
            "cik": "0001234567",
            "accession_no": "0001234567-26-012345",
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/1234567/"
                "000123456726099999/example-s1.htm"
            ),
        }
        failures = _sec_identity_failures(filing)
        self.assertTrue(any("accession directory" in item for item in failures))

    def test_query_string_cannot_mask_wrong_accession_directory(self):
        filing = {
            "cik": "0001234567",
            "accession_no": "0001234567-26-012345",
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/1234567/"
                "000123456726099999/example-s1.htm?expected=000123456726012345"
            ),
        }
        failures = _sec_identity_failures(filing)
        self.assertIn("SEC URL is not a canonical SEC Archives filing URL", failures)

    def test_filename_cannot_mask_wrong_accession_directory(self):
        filing = {
            "cik": "0001234567",
            "accession_no": "0001234567-26-012345",
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/1234567/"
                "000123456726099999/000123456726012345-s1.htm"
            ),
        }
        failures = _sec_identity_failures(filing)
        self.assertTrue(any("accession directory" in item for item in failures))


if __name__ == "__main__":
    unittest.main()

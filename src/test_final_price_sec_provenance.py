import json
import re
import unittest
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"
ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SEC_ARCHIVES_PREFIX = "https://www.sec.gov/Archives/edgar/data/"


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
            accession = str(filing.get("accession_no") or "").strip()
            sec_url = str(filing.get("sec_url") or "").strip()
            offering_price = filing.get("offering_price")

            if not isinstance(offering_price, (int, float)) or offering_price <= 0:
                failures.append(f"{label}: priced 424B4 lacks a positive Final IPO Price")

            if not ACCESSION_PATTERN.fullmatch(accession):
                failures.append(
                    f"{label}: priced 424B4 lacks a canonical SEC accession number: {accession!r}"
                )

            if not sec_url.startswith(SEC_ARCHIVES_PREFIX):
                failures.append(f"{label}: priced 424B4 does not link to an SEC Archives filing")
            elif accession and accession.replace("-", "") not in sec_url.replace("-", ""):
                failures.append(
                    f"{label}: priced-row SEC URL does not match accession {accession}"
                )

        self.assertGreater(checked, 0, "No priced 424B4 rows were available to validate")
        self.assertEqual(
            failures,
            [],
            "Final IPO Price SEC provenance failures: " + "; ".join(failures[:10]),
        )


if __name__ == "__main__":
    unittest.main()

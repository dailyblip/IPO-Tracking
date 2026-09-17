import json
import unittest
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"


class PersonRealizedCashIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        cls.filings = payload.get("filings", []) if isinstance(payload, dict) else payload

    def test_unsourced_holder_realized_cash_is_not_published(self):
        populated = []
        for filing in self.filings:
            for person in filing.get("people") or []:
                if not isinstance(person, dict):
                    continue
                if person.get("cash_realized_ipo") in (None, ""):
                    continue
                company = filing.get("company") or filing.get("id") or "<unknown issuer>"
                holder = person.get("name") or "<unknown holder>"
                populated.append(f"{company} / {holder}")

        self.assertEqual(
            populated,
            [],
            "Holder-level realized cash must remain blank without explicit public "
            "holder-level proceeds provenance; public offer price x shares sold is "
            "not authoritative realized cash: " + "; ".join(populated[:10]),
        )


if __name__ == "__main__":
    unittest.main()

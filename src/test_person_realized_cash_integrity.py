import json
import unittest
from decimal import Decimal, InvalidOperation
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"


def _number(value):
    if value in (None, "", "—") or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).replace(",", "").replace("$", "").strip())
    except (InvalidOperation, TypeError, ValueError):
        return None


class PersonRealizedCashIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        cls.filings = payload.get("filings", []) if isinstance(payload, dict) else payload

    def test_realized_cash_uses_authoritative_final_ipo_price(self):
        failures = []
        checked = 0

        for filing in self.filings:
            for person in filing.get("people") or []:
                if not isinstance(person, dict):
                    continue

                realized = _number(person.get("cash_realized_ipo"))
                if realized is None:
                    continue

                checked += 1
                company = filing.get("company") or filing.get("id") or "<unknown issuer>"
                holder = person.get("name") or "<unknown holder>"
                label = f"{company} / {holder}"
                form = str(filing.get("form") or "").strip().upper()
                stage = str(filing.get("stage") or "").strip().casefold()
                final_price = _number(filing.get("offering_price"))
                sold = _number(person.get("shares_sold_ipo"))

                if form != "424B4" or stage != "priced":
                    failures.append(f"{label}: realized cash exists outside a priced 424B4")
                    continue
                if final_price is None or final_price <= 0:
                    failures.append(
                        f"{label}: realized cash exists without authoritative Final IPO Price"
                    )
                    continue
                if sold is None or sold <= 0:
                    failures.append(
                        f"{label}: realized cash exists without supported shares_sold_ipo"
                    )
                    continue

                expected = sold * final_price
                if abs(realized - expected) > Decimal("0.01"):
                    failures.append(
                        f"{label}: cash_realized_ipo {realized} != "
                        f"{sold} shares x ${final_price} = {expected}"
                    )

        self.assertGreater(
            checked,
            0,
            "No populated holder-level IPO realized-cash values were available to validate",
        )
        self.assertEqual(
            failures,
            [],
            "Published realized-cash integrity failures: " + "; ".join(failures[:10]),
        )


if __name__ == "__main__":
    unittest.main()

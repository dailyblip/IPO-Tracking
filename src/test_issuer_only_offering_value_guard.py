import json
import unittest
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"
ISSUER_ONLY_MARKER = "explicit issuer-only cover statement"


def _number(value):
    if value in (None, "", "—"):
        return None
    try:
        return float(str(value).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None


class IssuerOnlyOfferingValueGuardTests(unittest.TestCase):
    def test_priced_issuer_only_offerings_reconcile_to_final_price(self):
        """Issuer-only 424B4 economics must reconcile without assuming a secondary block.

        A final prospectus source explicitly identified as issuer-only is affirmative
        evidence that the base offering is primary shares only. For those records,
        the published offering value must reconcile to primary shares times Final
        IPO Price, and a positive secondary share count is contradictory evidence.
        """
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        filings = payload.get("filings", []) if isinstance(payload, dict) else payload
        failures = []
        checked = 0

        for filing in filings:
            if str(filing.get("form") or "").strip().upper() != "424B4":
                continue
            if str(filing.get("stage") or "").strip().casefold() != "priced":
                continue
            source = str(filing.get("offering_size_source") or "").strip().casefold()
            if ISSUER_ONLY_MARKER not in source:
                continue

            checked += 1
            label = filing.get("company") or filing.get("id") or "unknown filing"
            value = _number(filing.get("value"))
            primary = _number(filing.get("primary_offering_shares"))
            secondary = _number(filing.get("secondary_offering_shares"))
            final_price = _number(filing.get("offering_price"))

            if None in (value, primary, final_price):
                failures.append(
                    f"{label}: issuer-only source lacks value, primary shares, or Final IPO Price"
                )
                continue
            if value <= 0 or primary <= 0 or final_price <= 0:
                failures.append(f"{label}: issuer-only economics must be positive")
                continue
            if secondary is not None and secondary > 0:
                failures.append(
                    f"{label}: issuer-only source conflicts with secondary shares {secondary:g}"
                )
                continue

            expected = primary * final_price
            tolerance = max(1.0, expected * 0.000001)
            if abs(value - expected) > tolerance:
                failures.append(
                    f"{label}: offering value {value:g} does not match issuer-only "
                    f"primary shares {primary:g} * Final IPO Price {final_price:g} = {expected:g}"
                )

        self.assertGreater(checked, 0, "No priced issuer-only 424B4 records were available to validate")
        self.assertEqual(
            failures,
            [],
            "Issuer-only offering-value reconciliation failures: " + "; ".join(failures[:10]),
        )


if __name__ == "__main__":
    unittest.main()

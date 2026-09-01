import json
import math
import unittest
from pathlib import Path


def _as_number(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


class PublishedPersonSaleIntegrityTests(unittest.TestCase):
    def test_published_holder_sales_have_authoritative_secondary_support(self):
        root = Path(__file__).resolve().parents[1]
        payload = json.loads((root / "docs" / "data" / "filings.json").read_text(encoding="utf-8"))
        failures = []

        for filing in payload.get("filings") or []:
            company = filing.get("company") or filing.get("id") or "<unknown issuer>"
            secondary = _as_number(filing.get("secondary_offering_shares"))

            for person in filing.get("people") or []:
                if not isinstance(person, dict):
                    continue
                sold_raw = person.get("shares_sold_ipo")
                if sold_raw in (None, ""):
                    continue

                holder = person.get("name") or "<unknown holder>"
                label = f"{company} / {holder}"
                sold = _as_number(sold_raw)
                if sold is None or sold <= 0:
                    failures.append(f"{label}: shares_sold_ipo must be a positive finite number")
                    continue

                if filing.get("form") != "424B4" or filing.get("stage") != "Priced":
                    failures.append(f"{label}: holder IPO sale appears outside a priced 424B4")

                if secondary is None or secondary <= 0:
                    failures.append(f"{label}: holder IPO sale lacks filing-level secondary-offering support")
                elif sold > secondary:
                    failures.append(
                        f"{label}: holder sale {sold:g} exceeds filing-level secondary shares {secondary:g}"
                    )

                before_raw = person.get("shares_before_ipo")
                if before_raw not in (None, ""):
                    before = _as_number(before_raw)
                    if before is None or before < 0:
                        failures.append(f"{label}: shares_before_ipo is invalid")
                    elif sold > before:
                        failures.append(
                            f"{label}: holder sale {sold:g} exceeds disclosed pre-IPO shares {before:g}"
                        )

        self.assertFalse(
            failures,
            "Published holder-level IPO sale integrity failures:\n- " + "\n- ".join(failures),
        )


if __name__ == "__main__":
    unittest.main()

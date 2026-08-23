import json
import unittest
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"


def _number(value):
    if value in (None, "", "—"):
        return None
    try:
        return float(str(value).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None


class PublishedResearchMonitorDataIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        cls.filings = payload.get("filings", []) if isinstance(payload, dict) else payload

    def test_exact_offering_components_reconcile_with_published_value(self):
        """Reject published offering values that contradict exact base-offering math.

        When the public feed has both primary and secondary base-offering share counts,
        plus the final IPO price, the displayed offering value must equal
        (primary + secondary) * final price. Over-allotment/greenshoe shares are not
        part of this base-offering calculation.
        """
        checked = 0
        for filing in self.filings:
            primary = _number(filing.get("primary_offering_shares"))
            secondary = _number(filing.get("secondary_offering_shares"))
            price = _number(filing.get("offering_price"))
            value = _number(filing.get("value"))
            if None in (primary, secondary, price, value):
                continue

            expected = (primary + secondary) * price
            tolerance = max(1.0, expected * 0.000001)
            self.assertAlmostEqual(
                value,
                expected,
                delta=tolerance,
                msg=(
                    f"{filing.get('company') or filing.get('id')}: published offering "
                    f"value {value} does not match ({primary} + {secondary}) * {price} "
                    f"= {expected}"
                ),
            )
            checked += 1

        # This guard prevents the regression test from silently becoming vacuous if
        # field names or export behavior change.
        self.assertGreater(checked, 0, "No filings had exact offering components to validate")


if __name__ == "__main__":
    unittest.main()

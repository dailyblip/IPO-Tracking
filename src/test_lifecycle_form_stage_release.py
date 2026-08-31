import json
import unittest
from datetime import date
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"


def _number(value):
    if value in (None, "", "—") or isinstance(value, bool):
        return None
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def _iso_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


class LifecycleFormStageReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        cls.filings = payload.get("filings", []) if isinstance(payload, dict) else []

    def test_supported_forms_cannot_publish_with_stage_drift(self):
        """S-1 history is pre-pricing; final 424B4 rows are priced."""
        failures = []
        expected_stage = {
            "S-1": "pre-pricing",
            "S-1/A": "pre-pricing",
            "424B4": "priced",
        }

        for filing in self.filings:
            form = str(filing.get("form") or "").strip().upper()
            if form not in expected_stage:
                continue
            stage = str(filing.get("stage") or "").strip().casefold()
            if stage != expected_stage[form]:
                label = filing.get("company") or filing.get("id") or "unknown filing"
                failures.append(
                    f"{label}: {form} published as {filing.get('stage')!r}, "
                    f"expected {expected_stage[form]!r}"
                )

        self.assertEqual(
            failures,
            [],
            "Published lifecycle form/stage drift: " + "; ".join(failures[:10]),
        )

    def test_s1_rows_cannot_publish_final_pricing_metadata(self):
        """A genuinely pre-pricing registration row cannot carry final IPO facts."""
        failures = []
        for filing in self.filings:
            form = str(filing.get("form") or "").strip().upper()
            if form not in {"S-1", "S-1/A"}:
                continue
            label = filing.get("company") or filing.get("id") or "unknown filing"
            if str(filing.get("pricing_date") or "").strip():
                failures.append(f"{label}: {form} retains Pricing Date")
            if _number(filing.get("offering_price")) is not None:
                failures.append(f"{label}: {form} retains Final IPO Price")

        self.assertEqual(
            failures,
            [],
            "Pre-pricing rows contain final pricing metadata: " + "; ".join(failures[:10]),
        )

    def test_424b4_rows_cannot_escape_final_pricing_requirements_via_stage_drift(self):
        """Every qualifying final prospectus needs canonical final pricing metadata."""
        failures = []
        checked = 0
        today = date.today()
        for filing in self.filings:
            if str(filing.get("form") or "").strip().upper() != "424B4":
                continue
            checked += 1
            label = filing.get("company") or filing.get("id") or "unknown filing"
            pricing_date = _iso_date(filing.get("pricing_date"))
            final_price = _number(filing.get("offering_price"))
            if pricing_date is None:
                failures.append(f"{label}: 424B4 lacks canonical Pricing Date")
            elif pricing_date > today:
                failures.append(f"{label}: 424B4 Pricing Date is in the future")
            if final_price is None or final_price <= 0:
                failures.append(f"{label}: 424B4 lacks positive Final IPO Price")

        self.assertGreater(checked, 0, "No 424B4 rows were available to validate")
        self.assertEqual(
            failures,
            [],
            "Final prospectus pricing failures: " + "; ".join(failures[:10]),
        )


if __name__ == "__main__":
    unittest.main()

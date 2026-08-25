import json
import unittest
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"
HISTORICAL_STANFORD_START = "2026-06-01"


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

    def test_june_present_confirmed_stanford_owners_are_publishable_and_explainable(self):
        """Keep the required historical Stanford signal verifiable in the live feed.

        Cardinal red is reserved for confirmed Stanford-affiliated beneficial owners.
        A published confirmed owner therefore must be a natural person with a disclosed
        positive share position and the current Confidence 5/5 evidence note format.
        The final assertion prevents the June 1 historical backfill from silently
        disappearing while UI-only tests continue to pass.
        """
        confirmed = []
        for filing in self.filings:
            filed = str(filing.get("filed") or "")
            if not filed or filed < HISTORICAL_STANFORD_START:
                continue
            for person in filing.get("people") or []:
                if not isinstance(person, dict) or person.get("stanford_university_bio") is not True:
                    continue

                label = f"{filing.get('company') or filing.get('id')} / {person.get('name')}"
                shares = _number(person.get("shares"))
                source = str(person.get("stanford_source") or "").strip()

                self.assertEqual(
                    str(person.get("holder_type") or "").casefold(),
                    "individual",
                    msg=f"{label}: confirmed Stanford record is not an individual",
                )
                self.assertIsNotNone(shares, msg=f"{label}: confirmed Stanford owner has no disclosed shares")
                self.assertGreater(shares, 0, msg=f"{label}: confirmed Stanford owner has no positive share position")
                self.assertTrue(
                    source.startswith("Confidence 5/5 — "),
                    msg=f"{label}: confirmed Stanford owner lacks a Confidence 5/5 connection note",
                )
                self.assertIn(
                    "Stanford University",
                    source,
                    msg=f"{label}: Stanford connection note does not identify Stanford University",
                )
                confirmed.append(label)

        self.assertGreater(
            len(confirmed),
            0,
            "No confirmed Stanford beneficial owner is published for the June 1, 2026-present backfill window",
        )


if __name__ == "__main__":
    unittest.main()

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

    def test_populated_offering_values_have_source_and_high_confidence(self):
        """Known IPO sizes need strong provenance; a genuinely unknown size may stay blank."""
        failures = []
        for filing in self.filings:
            label = filing.get("company") or filing.get("id") or "unknown filing"
            raw_value = filing.get("value")
            value = _number(raw_value)
            source = str(filing.get("offering_size_source") or "").strip()
            confidence = str(filing.get("offering_size_confidence") or "").strip()

            if raw_value not in (None, "", "—") and value is None:
                failures.append(f"{label}: offering value is populated but invalid: {raw_value!r}")
                continue
            if value is None:
                continue
            if value <= 0:
                failures.append(f"{label}: populated offering value must be positive")
            if not source:
                failures.append(f"{label}: populated offering value lacks source provenance")
            if confidence.casefold() != "high":
                failures.append(
                    f"{label}: populated offering value confidence is {confidence or 'missing'}, expected High"
                )

        self.assertEqual(
            failures,
            [],
            "Published IPO-size provenance failures: " + "; ".join(failures[:10]),
        )

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

        self.assertGreater(checked, 0, "No filings had exact offering components to validate")

    def test_public_stanford_sources_do_not_expose_internal_processing_text(self):
        """Operational failures and internal grader notes must never be public evidence."""
        forbidden_markers = (
            "grading failed to run",
            "research request failed",
            "insufficient_quota",
            "no credits remaining",
            "person-level stanford grading skipped",
        )
        leaks = []
        for filing in self.filings:
            for person in filing.get("people") or []:
                if not isinstance(person, dict):
                    continue
                source = str(person.get("stanford_source") or "").strip()
                folded = source.casefold()
                marker = next((item for item in forbidden_markers if item in folded), None)
                if marker:
                    leaks.append(
                        f"{filing.get('company') or filing.get('id')} / "
                        f"{person.get('name')}: {marker}"
                    )

        self.assertEqual(
            leaks,
            [],
            "Public Stanford evidence contains internal processing text: " + "; ".join(leaks[:10]),
        )

    def test_june_present_confirmed_stanford_signal_is_explainable_and_red_eligible(self):
        """Keep the required June-present Stanford signal verifiable in the live feed.

        Confirmed affiliation and red-text eligibility are deliberately separate:
        every confirmed Stanford person needs a 5/5 evidence note, while Cardinal red
        additionally requires a disclosed positive beneficial-owner share position.
        At least one June-present record must satisfy the full red-text gate so the
        historical Stanford signal cannot silently disappear from the public feed.
        """
        confirmed = []
        red_eligible = []
        for filing in self.filings:
            filed = str(filing.get("filed") or "")
            if not filed or filed < HISTORICAL_STANFORD_START:
                continue
            for person in filing.get("people") or []:
                if not isinstance(person, dict) or person.get("stanford_university_bio") is not True:
                    continue

                label = f"{filing.get('company') or filing.get('id')} / {person.get('name')}"
                source = str(person.get("stanford_source") or "").strip()
                self.assertEqual(
                    str(person.get("holder_type") or "").casefold(),
                    "individual",
                    msg=f"{label}: confirmed Stanford record is not an individual",
                )
                self.assertTrue(
                    source.startswith("Confidence 5/5 — "),
                    msg=f"{label}: confirmed Stanford person lacks a Confidence 5/5 connection note",
                )
                self.assertIn(
                    "Stanford University",
                    source,
                    msg=f"{label}: Stanford connection note does not identify Stanford University",
                )
                confirmed.append(label)

                shares = _number(person.get("shares"))
                if shares is not None and shares > 0:
                    red_eligible.append(label)

        self.assertGreater(
            len(confirmed),
            0,
            "No confirmed Stanford affiliation is published for the June 1, 2026-present backfill window",
        )
        self.assertGreater(
            len(red_eligible),
            0,
            "No confirmed Stanford beneficial owner with disclosed shares is published for Cardinal-red highlighting",
        )


if __name__ == "__main__":
    unittest.main()
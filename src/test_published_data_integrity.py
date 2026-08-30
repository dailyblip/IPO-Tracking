import json
import unittest
from datetime import date
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


def _iso_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


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

    def test_public_market_quotes_only_exist_on_priced_424b4_rows(self):
        """A live quote is valid only after authoritative IPO pricing is established."""
        failures = []
        for filing in self.filings:
            current_price = _number(filing.get("current_price"))
            if current_price is None:
                continue

            label = filing.get("company") or filing.get("id") or "unknown filing"
            form = str(filing.get("form") or "").strip().upper()
            stage = str(filing.get("stage") or "").strip().casefold()
            if form != "424B4":
                failures.append(
                    f"{label}: Current Price is attached to non-424B4 form {filing.get('form')!r}"
                )
            if stage != "priced":
                failures.append(
                    f"{label}: Current Price is attached to non-priced stage {filing.get('stage')!r}"
                )
            if _number(filing.get("offering_price")) is None:
                failures.append(f"{label}: Current Price exists without authoritative Final IPO Price")
            if not str(filing.get("pricing_date") or "").strip():
                failures.append(f"{label}: Current Price exists without Pricing Date")

        self.assertEqual(
            failures,
            [],
            "Published quote lifecycle failures: " + "; ".join(failures[:10]),
        )

    def test_prepricing_rows_publish_no_market_derived_values(self):
        """Pre-pricing rows must not retain live quotes or quote-derived holder values."""
        failures = []
        filing_market_fields = ("current_price", "price_updated")
        person_market_fields = ("cash_value", "liquid_value", "locked_value", "valuation_as_of")

        for filing in self.filings:
            if str(filing.get("stage") or "").strip().casefold() != "pre-pricing":
                continue

            label = filing.get("company") or filing.get("id") or "unknown filing"
            for field in filing_market_fields:
                if filing.get(field) not in (None, "", "—"):
                    failures.append(f"{label}: pre-pricing row retains {field}")

            for person in filing.get("people") or []:
                if not isinstance(person, dict):
                    continue
                for field in person_market_fields:
                    if person.get(field) not in (None, "", "—"):
                        failures.append(
                            f"{label} / {person.get('name')}: pre-pricing row retains {field}"
                        )

        self.assertEqual(
            failures,
            [],
            "Pre-pricing market-data leaks: " + "; ".join(failures[:10]),
        )

    def test_priced_rows_have_authoritative_pricing_metadata(self):
        """Priced 424B4 rows need final pricing facts and SEC provenance for any filing range."""
        failures = []
        checked = 0
        for filing in self.filings:
            form = str(filing.get("form") or "").strip().upper()
            stage = str(filing.get("stage") or "").strip().casefold()
            if form != "424B4" or stage != "priced":
                continue

            checked += 1
            label = filing.get("company") or filing.get("id") or "unknown filing"
            if _number(filing.get("offering_price")) is None:
                failures.append(f"{label}: priced row lacks Final IPO Price")
            if not str(filing.get("pricing_date") or "").strip():
                failures.append(f"{label}: priced row lacks Pricing Date")

            preliminary = str(
                filing.get("filing_price") or filing.get("price_range") or ""
            ).strip()
            if not preliminary:
                continue

            source = filing.get("filing_price_source")
            if not isinstance(source, dict):
                failures.append(f"{label}: populated Filing Price lacks source provenance")
                continue
            if str(source.get("source") or "").strip().casefold() != "sec edgar":
                failures.append(f"{label}: Filing Price source is not SEC EDGAR")
            if str(source.get("form") or "").strip().upper() not in {"S-1", "S-1/A"}:
                failures.append(f"{label}: Filing Price source is not S-1/S-1A")
            for field in ("filing_date", "accession_no", "sec_url"):
                if not str(source.get(field) or "").strip():
                    failures.append(f"{label}: Filing Price source lacks {field}")

        self.assertGreater(checked, 0, "No priced 424B4 rows were available to validate")
        self.assertEqual(
            failures,
            [],
            "Published pricing metadata failures: " + "; ".join(failures[:10]),
        )

    def test_priced_rows_have_canonical_chronological_pricing_dates(self):
        """Reject populated pricing metadata that encodes an impossible IPO lifecycle."""
        failures = []
        checked = 0
        today = date.today()

        for filing in self.filings:
            form = str(filing.get("form") or "").strip().upper()
            stage = str(filing.get("stage") or "").strip().casefold()
            if form != "424B4" or stage != "priced":
                continue

            checked += 1
            label = filing.get("company") or filing.get("id") or "unknown filing"
            raw_pricing_date = str(filing.get("pricing_date") or "").strip()
            pricing_date = _iso_date(raw_pricing_date)
            filed = _iso_date(filing.get("filed"))
            initial_filing_date = _iso_date(filing.get("filing_date"))

            if pricing_date is None:
                failures.append(f"{label}: Pricing Date is missing or non-canonical: {raw_pricing_date!r}")
                continue
            if pricing_date > today:
                failures.append(f"{label}: Pricing Date is in the future: {raw_pricing_date}")
            if filed is None:
                failures.append(f"{label}: 424B4 Filed date is missing or non-canonical")
            elif pricing_date > filed:
                failures.append(
                    f"{label}: Pricing Date {pricing_date.isoformat()} occurs after 424B4 Filed {filed.isoformat()}"
                )
            if initial_filing_date is not None and initial_filing_date > pricing_date:
                failures.append(
                    f"{label}: initial Filing Date {initial_filing_date.isoformat()} occurs after Pricing Date {pricing_date.isoformat()}"
                )

        self.assertGreater(checked, 0, "No priced 424B4 rows were available to validate")
        self.assertEqual(
            failures,
            [],
            "Published IPO chronology failures: " + "; ".join(failures[:10]),
        )

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

import json
import unittest
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"
_EMPTY = (None, "", "—")
_FINAL_PERSON_FIELDS = ("ipo_value", "cash_realized_ipo")
_FINAL_SIGNAL_MARKERS = ("offering priced at", "offering raised approximately")


class PublishedPrepricingLifecycleIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        cls.filings = payload.get("filings", []) if isinstance(payload, dict) else payload

    def test_public_s1_rows_never_publish_completed_ipo_economics(self):
        failures = []
        for filing in self.filings:
            form = str(filing.get("form") or "").strip().upper()
            if form not in {"S-1", "S-1/A"}:
                continue

            label = filing.get("company") or filing.get("id") or "unknown filing"
            if str(filing.get("stage") or "").strip().casefold() != "pre-pricing":
                failures.append(
                    f"{label}: {form} row has non-pre-pricing stage {filing.get('stage')!r}"
                )
            if filing.get("pricing_date") not in _EMPTY:
                failures.append(f"{label}: pre-pricing {form} row retains Pricing Date")
            if filing.get("offering_price") not in _EMPTY:
                failures.append(f"{label}: pre-pricing {form} row retains Final IPO Price")

            for person in filing.get("people") or []:
                if not isinstance(person, dict):
                    continue
                person_label = person.get("name") or "unknown person"
                for field in _FINAL_PERSON_FIELDS:
                    if person.get(field) not in _EMPTY:
                        failures.append(
                            f"{label} / {person_label}: pre-pricing row retains {field}"
                        )

            for signal in filing.get("signals") or []:
                if not isinstance(signal, str):
                    continue
                folded = signal.casefold()
                if any(marker in folded for marker in _FINAL_SIGNAL_MARKERS):
                    failures.append(
                        f"{label}: pre-pricing row retains final-pricing signal {signal!r}"
                    )

        self.assertGreater(len(self.filings), 0, "Public feed is empty")
        self.assertEqual(
            failures,
            [],
            "Published pre-pricing lifecycle failures: " + "; ".join(failures[:10]),
        )


if __name__ == "__main__":
    unittest.main()

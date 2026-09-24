import json
import unittest
from datetime import date
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"


def _iso_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def filing_price_provenance_failures(filings):
    """Return impossible preliminary-price provenance states for priced IPOs."""
    failures = []
    for filing in filings:
        if not isinstance(filing, dict):
            continue
        form = str(filing.get("form") or "").strip().upper()
        stage = str(filing.get("stage") or "").strip().casefold()
        if form != "424B4" or stage != "priced":
            continue

        preliminary = str(
            filing.get("filing_price") or filing.get("price_range") or ""
        ).strip()
        if not preliminary:
            continue

        label = filing.get("company") or filing.get("id") or "unknown filing"
        source = filing.get("filing_price_source")
        if not isinstance(source, dict):
            failures.append(f"{label}: populated Filing Price lacks source provenance")
            continue

        if str(source.get("source") or "").strip().casefold() != "sec edgar":
            failures.append(f"{label}: Filing Price source is not SEC EDGAR")
        if str(source.get("form") or "").strip().upper() not in {"S-1", "S-1/A"}:
            failures.append(f"{label}: Filing Price source is not S-1/S-1A")

        source_date = _iso_date(source.get("filing_date"))
        pricing_date = _iso_date(filing.get("pricing_date"))
        final_filed = _iso_date(filing.get("filed"))
        if source_date is None:
            failures.append(f"{label}: Filing Price source filing_date is missing or non-canonical")
        if pricing_date is None:
            failures.append(f"{label}: Pricing Date is missing or non-canonical")
        if final_filed is None:
            failures.append(f"{label}: final 424B4 Filed date is missing or non-canonical")
        if source_date is not None and pricing_date is not None and source_date > pricing_date:
            failures.append(
                f"{label}: preliminary Filing Price source {source_date.isoformat()} "
                f"occurs after Pricing Date {pricing_date.isoformat()}"
            )
        if source_date is not None and final_filed is not None and source_date > final_filed:
            failures.append(
                f"{label}: preliminary Filing Price source {source_date.isoformat()} "
                f"occurs after final 424B4 Filed {final_filed.isoformat()}"
            )
    return failures


class PublishedFilingPriceProvenanceChronologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        cls.filings = payload.get("filings", []) if isinstance(payload, dict) else payload

    def test_published_preliminary_price_provenance_is_chronological(self):
        failures = filing_price_provenance_failures(self.filings)
        self.assertEqual(
            failures,
            [],
            "Published Filing Price provenance chronology failures: "
            + "; ".join(failures[:10]),
        )

    def test_future_dated_preliminary_source_is_rejected(self):
        failures = filing_price_provenance_failures(
            [
                {
                    "company": "Example Systems Inc.",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-09-10",
                    "pricing_date": "2026-09-09",
                    "filing_price": "$17.00–$19.00",
                    "filing_price_source": {
                        "source": "SEC EDGAR",
                        "form": "S-1/A",
                        "filing_date": "2026-09-11",
                        "accession_no": "0000000000-26-000001",
                        "sec_url": "https://www.sec.gov/Archives/example",
                    },
                }
            ]
        )
        self.assertTrue(
            any("occurs after Pricing Date" in failure for failure in failures),
            failures,
        )
        self.assertTrue(
            any("occurs after final 424B4 Filed" in failure for failure in failures),
            failures,
        )


if __name__ == "__main__":
    unittest.main()

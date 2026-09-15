from __future__ import annotations

import unittest

from dashboard_export import SCHEMA_VERSION
from feed_schema_contract import validate_payload


class FeedSchemaFinalChronologyTests(unittest.TestCase):
    def _payload(self, **overrides):
        filing = {
            "id": "chronology-1",
            "company": "Example Corp.",
            "ticker": "EXM",
            "cik": "0001234567",
            "accession_no": "0001193125-26-123456",
            "form": "424B4",
            "filed": "2026-08-20",
            "filing_date": "2026-08-01",
            "pricing_date": "2026-08-20",
            "stage": "Priced",
            "priority": "Medium",
            "status": "New",
            "value": None,
            "value_label": None,
            "offering_price": 17.0,
            "people_count": 0,
            "signals": [],
            "people": [],
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/1234567/"
                "000119312526123456/example-424b4.htm"
            ),
        }
        filing.update(overrides)
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": "2026-09-15T00:00:00+00:00",
            "source": "SEC EDGAR",
            "filings": [filing],
        }

    def test_sec_filed_date_must_be_real_calendar_date(self):
        failures = validate_payload(self._payload(filed="2026-02-30"))
        self.assertTrue(
            any("SEC filing date must be a canonical calendar date" in failure for failure in failures),
            failures,
        )

    def test_sec_filed_date_cannot_be_future(self):
        failures = validate_payload(self._payload(filed="2999-01-01"))
        self.assertTrue(
            any("SEC filing date cannot be in the future" in failure for failure in failures),
            failures,
        )

    def test_pricing_date_cannot_postdate_final_424b4_filing(self):
        failures = validate_payload(
            self._payload(filed="2026-08-19", pricing_date="2026-08-20")
        )
        self.assertTrue(
            any("Pricing Date cannot postdate the final 424B4 filing date" in failure for failure in failures),
            failures,
        )

    def test_valid_final_filing_chronology_is_allowed(self):
        self.assertEqual([], validate_payload(self._payload()))


if __name__ == "__main__":
    unittest.main()

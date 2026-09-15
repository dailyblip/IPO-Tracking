from __future__ import annotations

import json
import unittest
from pathlib import Path

from dashboard_export import PUBLIC_FILING_FIELDS, PUBLIC_PERSON_FIELDS, SCHEMA_VERSION
from feed_schema_contract import load_schema, validate_file, validate_payload

ROOT = Path(__file__).resolve().parents[1]


class FeedSchemaContractTests(unittest.TestCase):
    def _filing(self, **overrides):
        filing = {
            "id": "test-1",
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
            "value": 150000000,
            "value_label": "$150M",
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
        return filing

    def _payload(self, filing):
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": "2026-08-28T00:00:00+00:00",
            "source": "SEC EDGAR",
            "filings": [filing],
        }

    def _filing_price_source(self, **overrides):
        source = {
            "source": "SEC EDGAR",
            "form": "S-1/A",
            "filing_date": "2026-08-18",
            "accession_no": "0001193125-26-123455",
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/1234567/"
                "000119312526123455/example-s1a.htm"
            ),
        }
        source.update(overrides)
        return source

    def _ownership_source(self, **overrides):
        source = self._filing_price_source()
        source.update(overrides)
        return source

    def test_checked_in_feed_matches_registered_schema(self):
        failures = validate_file(ROOT / "docs" / "data" / "filings.json")
        self.assertEqual([], failures, "\n".join(failures))

    def test_v1_schema_covers_public_export_allowlists(self):
        schema = load_schema(SCHEMA_VERSION)
        filing_fields = set(schema["$defs"]["filing"]["properties"])
        person_fields = set(schema["$defs"]["person"]["properties"])
        self.assertTrue(PUBLIC_FILING_FIELDS <= filing_fields)
        self.assertTrue(PUBLIC_PERSON_FIELDS <= person_fields)
        self.assertEqual(SCHEMA_VERSION, schema["properties"]["schema_version"]["const"])

    def test_unknown_top_level_field_is_rejected(self):
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": "2026-08-28T00:00:00+00:00",
            "source": "SEC EDGAR",
            "filings": [],
            "unexpected": True,
        }
        self.assertTrue(validate_payload(payload))

    def test_valid_sec_ownership_provenance_is_accepted(self):
        filing = self._filing(
            people_count=1,
            people=[{"name": "Jane Example", "stanford_university_bio": False}],
            ownership_source=self._ownership_source(),
        )
        self.assertEqual([], validate_payload(self._payload(filing)))

    def test_ownership_provenance_requires_named_owners(self):
        filing = self._filing(ownership_source=self._ownership_source())
        failures = validate_payload(self._payload(filing))
        self.assertTrue(
            any("cannot exist without named owners" in failure for failure in failures),
            failures,
        )

    def test_ownership_provenance_rejects_cross_issuer_sec_url(self):
        filing = self._filing(
            people_count=1,
            people=[{"name": "Jane Example", "stanford_university_bio": False}],
            ownership_source=self._ownership_source(
                sec_url=(
                    "https://www.sec.gov/Archives/edgar/data/7654321/"
                    "000119312526123455/example-s1a.htm"
                )
            ),
        )
        failures = validate_payload(self._payload(filing))
        self.assertTrue(
            any("ownership SEC URL issuer CIK does not match row CIK" in failure for failure in failures),
            failures,
        )

    def test_unregistered_schema_version_is_rejected(self):
        payload = {
            "schema_version": 999,
            "generated_at": "2026-08-28T00:00:00+00:00",
            "source": "SEC EDGAR",
            "filings": [],
        }
        failures = validate_payload(payload)
        self.assertTrue(any("No public-feed schema is registered" in failure for failure in failures))

    def test_public_row_requires_canonical_issuer_cik(self):
        failures = validate_payload(self._payload(self._filing(cik="1234567")))
        self.assertTrue(
            any("canonical 10-digit issuer CIK" in failure for failure in failures),
            failures,
        )

    def test_public_row_requires_canonical_accession_number(self):
        failures = validate_payload(
            self._payload(self._filing(accession_no="000119312526123456"))
        )
        self.assertTrue(
            any("canonical SEC accession number" in failure for failure in failures),
            failures,
        )

    def test_public_row_rejects_cross_issuer_sec_url(self):
        failures = validate_payload(
            self._payload(
                self._filing(
                    sec_url=(
                        "https://www.sec.gov/Archives/edgar/data/7654321/"
                        "000119312526123456/example-424b4.htm"
                    )
                )
            )
        )
        self.assertTrue(
            any("SEC URL issuer CIK does not match row CIK" in failure for failure in failures),
            failures,
        )

    def test_public_row_rejects_wrong_accession_sec_url(self):
        failures = validate_payload(
            self._payload(
                self._filing(
                    sec_url=(
                        "https://www.sec.gov/Archives/edgar/data/1234567/"
                        "000119312526999999/example-424b4.htm"
                    )
                )
            )
        )
        self.assertTrue(
            any("accession directory does not match row accession" in failure for failure in failures),
            failures,
        )

    def test_public_row_rejects_noncanonical_sec_url(self):
        for suffix in ("?output=1", "#filing"):
            with self.subTest(suffix=suffix):
                filing = self._filing(sec_url=self._filing()["sec_url"] + suffix)
                failures = validate_payload(self._payload(filing))
                self.assertTrue(
                    any("canonical SEC Archives filing URL" in failure for failure in failures),
                    failures,
                )

    def test_prepricing_current_price_is_release_blocking(self):
        filing = self._filing(
            form="S-1/A",
            stage="Pre-pricing",
            pricing_date=None,
            offering_price=None,
            current_price=22.5,
        )
        failures = validate_payload(self._payload(filing))
        self.assertTrue(
            any("Current Price is permitted only for a 424B4/Priced" in failure for failure in failures),
            failures,
        )

    def test_priced_stage_requires_final_424b4_form(self):
        filing = self._filing(form="S-1/A", stage="Priced")
        failures = validate_payload(self._payload(filing))
        self.assertTrue(
            any("must pair form 424B4 with stage Priced" in failure for failure in failures),
            failures,
        )

    def test_final_424b4_requires_priced_stage(self):
        filing = self._filing(form="424B4", stage="Pre-pricing")
        failures = validate_payload(self._payload(filing))
        self.assertTrue(
            any("must pair form 424B4 with stage Priced" in failure for failure in failures),
            failures,
        )

    def test_priced_424b4_requires_positive_final_ipo_price(self):
        for invalid_price in (None, 0, -1):
            with self.subTest(invalid_price=invalid_price):
                filing = self._filing(offering_price=invalid_price)
                failures = validate_payload(self._payload(filing))
                self.assertTrue(
                    any("must have a positive Final IPO Price" in failure for failure in failures),
                    failures,
                )

    def test_priced_424b4_requires_canonical_pricing_date(self):
        filing = self._filing(pricing_date=None)
        failures = validate_payload(self._payload(filing))
        self.assertTrue(
            any("priced 424B4 must have a canonical Pricing Date" in failure for failure in failures),
            failures,
        )

    def test_initial_filing_date_after_pricing_date_is_release_blocking(self):
        filing = self._filing(
            filing_date="2026-08-21",
            pricing_date="2026-08-20",
        )
        failures = validate_payload(self._payload(filing))
        self.assertTrue(
            any("initial filing date cannot postdate Pricing Date" in failure for failure in failures),
            failures,
        )

    def test_valid_priced_current_price_state_is_allowed(self):
        filing = self._filing(
            current_price=19.25,
            price_updated="2026-08-21T15:30:00+00:00",
        )
        self.assertEqual([], validate_payload(self._payload(filing)))

    def test_filing_price_source_without_preliminary_price_is_rejected(self):
        filing = self._filing(
            filing_price=None,
            price_range=None,
            filing_price_source=self._filing_price_source(),
        )
        failures = validate_payload(self._payload(filing))
        self.assertTrue(
            any("provenance cannot remain populated" in failure for failure in failures),
            failures,
        )

    def test_priced_preliminary_price_without_source_is_rejected(self):
        filing = self._filing(
            filing_price="15-17",
            price_range="15-17",
            filing_price_source=None,
        )
        failures = validate_payload(self._payload(filing))
        self.assertTrue(
            any("lacks SEC S-1/S-1A provenance" in failure for failure in failures),
            failures,
        )

    def test_priced_filing_price_aliases_must_agree(self):
        filing = self._filing(
            filing_price="15-17",
            price_range="16-18",
            filing_price_source=self._filing_price_source(),
        )
        failures = validate_payload(self._payload(filing))
        self.assertTrue(any("filing_price and price_range disagree" in failure for failure in failures), failures)

    def test_filing_price_source_must_be_sec_registration_provenance(self):
        filing = self._filing(
            filing_price="15-17",
            price_range="15-17",
            filing_price_source=self._filing_price_source(source="Issuer", form="424B4"),
        )
        failures = validate_payload(self._payload(filing))
        self.assertTrue(any("source must be SEC EDGAR" in failure for failure in failures), failures)
        self.assertTrue(any("source must be S-1 or S-1/A" in failure for failure in failures), failures)

    def test_filing_price_source_after_pricing_date_is_rejected(self):
        filing = self._filing(
            filing_price="15-17",
            price_range="15-17",
            filing_price_source=self._filing_price_source(filing_date="2026-08-21"),
        )
        failures = validate_payload(self._payload(filing))
        self.assertTrue(any("cannot postdate Pricing Date" in failure for failure in failures), failures)

    def test_cross_issuer_filing_price_source_url_is_rejected(self):
        filing = self._filing(
            filing_price="15-17",
            price_range="15-17",
            filing_price_source=self._filing_price_source(
                sec_url=(
                    "https://www.sec.gov/Archives/edgar/data/7654321/"
                    "000119312526123455/example-s1a.htm"
                )
            ),
        )
        failures = validate_payload(self._payload(filing))
        self.assertTrue(any("issuer CIK does not match row CIK" in failure for failure in failures), failures)

    def test_wrong_accession_filing_price_source_url_is_rejected(self):
        filing = self._filing(
            filing_price="15-17",
            price_range="15-17",
            filing_price_source=self._filing_price_source(
                sec_url=(
                    "https://www.sec.gov/Archives/edgar/data/1234567/"
                    "000119312526999999/example-s1a.htm"
                )
            ),
        )
        failures = validate_payload(self._payload(filing))
        self.assertTrue(any("does not match source accession" in failure for failure in failures), failures)

    def test_priced_filing_price_requires_canonical_pricing_date(self):
        filing = self._filing(
            pricing_date=None,
            filing_price="15-17",
            price_range="15-17",
            filing_price_source=self._filing_price_source(),
        )
        failures = validate_payload(self._payload(filing))
        self.assertTrue(any("must have a canonical Pricing Date" in failure for failure in failures), failures)

    def test_filing_price_source_with_preliminary_price_is_valid(self):
        filing = self._filing(
            filing_price="15-17",
            price_range="15-17",
            filing_price_source=self._filing_price_source(),
        )
        self.assertEqual([], validate_payload(self._payload(filing)))

    def test_filing_price_source_with_registration_file_number_is_valid(self):
        filing = self._filing(
            filing_price="15-17",
            price_range="15-17",
            filing_price_source=self._filing_price_source(file_number="333-300001"),
        )
        self.assertEqual([], validate_payload(self._payload(filing)))


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import date, timedelta
from pathlib import Path

from final_pricing_release_gate import is_release_grade_final, sanitize_payload


class FinalPricingReleaseGateTests(unittest.TestCase):
    def _final(self, **updates):
        filing = {
            "id": "priced-ipo",
            "company": "Acme Robotics, Inc.",
            "cik": "0001234567",
            "accession_no": "0001234567-26-000001",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-08-24",
            "pricing_date": "2026-08-24",
            "offering_price": 18.0,
            "value": None,
            "filing_price": None,
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/1234567/"
                "000123456726000001/0001234567-26-000001-index.htm"
            ),
        }
        filing.update(updates)
        return filing

    def _prepricing(self, **updates):
        filing = {
            "id": "prepricing-ipo",
            "company": "Acme Robotics, Inc.",
            "cik": "0001234567",
            "accession_no": "0001234567-26-000010",
            "form": "S-1/A",
            "stage": "Pre-pricing",
            "filed": "2026-08-20",
            "value": None,
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/1234567/"
                "000123456726000010/0001234567-26-000010-index.htm"
            ),
        }
        filing.update(updates)
        return filing

    def test_release_grade_final_does_not_require_size_or_preliminary_price(self):
        self.assertTrue(is_release_grade_final(self._final()))

    def test_final_prospectus_requires_priced_stage(self):
        self.assertFalse(is_release_grade_final(self._final(stage="Pre-pricing")))
        self.assertFalse(is_release_grade_final(self._final(stage="")))

    def test_final_prospectus_requires_canonical_nonfuture_pricing_date(self):
        self.assertFalse(is_release_grade_final(self._final(pricing_date=None)))
        self.assertFalse(is_release_grade_final(self._final(pricing_date="08/24/2026")))
        future = (date.today() + timedelta(days=1)).isoformat()
        self.assertFalse(is_release_grade_final(self._final(pricing_date=future)))

    def test_final_prospectus_requires_canonical_nonfuture_filing_date(self):
        self.assertFalse(is_release_grade_final(self._final(filed=None)))
        self.assertFalse(is_release_grade_final(self._final(filed="08/24/2026")))
        future = (date.today() + timedelta(days=1)).isoformat()
        self.assertFalse(is_release_grade_final(self._final(filed=future)))

    def test_final_prospectus_rejects_pricing_after_final_filing(self):
        self.assertFalse(
            is_release_grade_final(
                self._final(filed="2026-08-24", pricing_date="2026-08-25")
            )
        )

    def test_final_prospectus_accepts_supported_registration_chronology(self):
        self.assertTrue(
            is_release_grade_final(
                self._final(
                    filing_date="2026-08-12",
                    pricing_date="2026-08-23",
                    filed="2026-08-24",
                )
            )
        )

    def test_final_prospectus_rejects_registration_after_pricing(self):
        self.assertFalse(
            is_release_grade_final(
                self._final(
                    filing_date="2026-08-25",
                    pricing_date="2026-08-23",
                    filed="2026-08-24",
                )
            )
        )

    def test_final_prospectus_rejects_malformed_registration_date_when_present(self):
        self.assertFalse(is_release_grade_final(self._final(filing_date="08/12/2026")))
        future = (date.today() + timedelta(days=1)).isoformat()
        self.assertFalse(is_release_grade_final(self._final(filing_date=future)))

    def test_final_prospectus_allows_blank_registration_date(self):
        self.assertTrue(is_release_grade_final(self._final(filing_date=None)))
        self.assertTrue(is_release_grade_final(self._final(filing_date="")))

    def test_final_prospectus_requires_positive_final_ipo_price(self):
        for value in (None, "", 0, -1, "unknown", float("nan"), True):
            with self.subTest(value=value):
                self.assertFalse(is_release_grade_final(self._final(offering_price=value)))

    def test_final_prospectus_requires_matching_sec_identity_provenance(self):
        wrong_accession = "0001234567-26-000002"
        cases = (
            {"cik": None},
            {"cik": ["0001234567"]},
            {"accession_no": None},
            {"accession_no": ["0001234567-26-000001"]},
            {"accession_no": "1234567-26-1"},
            {"sec_url": None},
            {
                "sec_url": (
                    "https://www.sec.gov/Archives/edgar/data/7654321/"
                    "000123456726000001/0001234567-26-000001-index.htm"
                )
            },
            {
                "sec_url": (
                    "https://www.sec.gov/Archives/edgar/data/1234567/"
                    f"{wrong_accession.replace('-', '')}/{wrong_accession}-index.htm"
                )
            },
            {
                "sec_url": (
                    "https://www.sec.gov/Archives/edgar/data/1234567/"
                    "000123456726000002/0001234567-26-000001-index.htm"
                )
            },
            {
                "sec_url": (
                    "https://www.sec.gov/Archives/edgar/data/1234567/"
                    "000123456726000001/0001234567-26-000002-index.htm"
                )
            },
            {
                "sec_url": (
                    "https://www.sec.gov/Archives/edgar/data/1234567/"
                    "000123456726000002/0001234567-26-000002-index.htm"
                    "?source=000123456726000001"
                )
            },
        )
        for updates in cases:
            with self.subTest(updates=updates):
                self.assertFalse(is_release_grade_final(self._final(**updates)))

    def test_prepricing_with_canonical_sec_identity_is_release_grade(self):
        self.assertTrue(is_release_grade_final(self._prepricing()))

    def test_prepricing_rejects_partial_or_stale_sec_identity_provenance(self):
        cases = (
            {"cik": None},
            {"accession_no": None},
            {"sec_url": None},
            {
                "sec_url": (
                    "https://www.sec.gov/Archives/edgar/data/7654321/"
                    "000123456726000010/0001234567-26-000010-index.htm"
                )
            },
            {
                "sec_url": (
                    "https://www.sec.gov/Archives/edgar/data/1234567/"
                    "000123456726000011/0001234567-26-000011-index.htm"
                    "?source=000123456726000010"
                )
            },
        )
        for updates in cases:
            with self.subTest(updates=updates):
                self.assertFalse(is_release_grade_final(self._prepricing(**updates)))

    def test_malformed_filing_entries_fail_closed(self):
        malformed = [None, "not a filing", ["bad"]]
        for filing in malformed:
            with self.subTest(filing=filing):
                self.assertFalse(is_release_grade_final(filing))

        good = self._final(id="good")
        payload, removed = sanitize_payload(
            {"schema_version": 1, "filings": [good, *malformed]}
        )
        self.assertEqual(payload["filings"], [good])
        self.assertEqual(removed, malformed)

    def test_prepricing_registration_rows_are_not_removed_by_final_gate(self):
        filing = {
            "id": "prepricing",
            "company": "Acme Robotics, Inc.",
            "form": "S-1/A",
            "stage": "Pre-pricing",
            "filed": "2026-08-20",
            "value": None,
        }
        payload, removed = sanitize_payload({"filings": [filing]})
        self.assertEqual(removed, [])
        self.assertEqual(payload["filings"], [filing])

    def test_unresolved_424b4_is_removed_after_reconciliation_opportunity(self):
        good = self._final(id="good")
        bad_stage = self._final(id="bad-stage", stage="Pre-pricing")
        bad_date = self._final(id="bad-date", pricing_date=None)
        bad_price = self._final(id="bad-price", offering_price=None)
        bad_identity = self._final(
            id="bad-identity", sec_url="https://www.sec.gov/edgar/search/"
        )

        payload, removed = sanitize_payload(
            {
                "schema_version": 1,
                "filings": [good, bad_stage, bad_date, bad_price, bad_identity],
            }
        )

        self.assertEqual([item["id"] for item in payload["filings"]], ["good"])
        self.assertEqual(
            [item["id"] for item in removed],
            ["bad-stage", "bad-date", "bad-price", "bad-identity"],
        )

    def _assert_writer_orders_final_gate(self, workflow_path):
        workflow = workflow_path.read_text(encoding="utf-8")
        pricing = workflow.index("python pricing_date_reconciler.py ../docs/data/filings.json")
        final_gate = workflow.index("python final_pricing_release_gate.py ../docs/data/filings.json")
        release_policy = workflow.index("python public_feed_policy.py ../docs/data/filings.json", pricing)
        self.assertLess(pricing, final_gate)
        self.assertLess(final_gate, release_policy)

    def test_daily_workflow_runs_gate_after_pricing_reconciliation(self):
        root = Path(__file__).resolve().parents[1]
        self._assert_writer_orders_final_gate(root / ".github" / "workflows" / "daily.yml")

    def test_ownership_refresh_runs_gate_after_pricing_reconciliation(self):
        root = Path(__file__).resolve().parents[1]
        workflow_path = root / ".github" / "workflows" / "ownership-refresh.yml"
        self._assert_writer_orders_final_gate(workflow_path)
        workflow = workflow_path.read_text(encoding="utf-8")
        self.assertIn("- 'src/final_pricing_release_gate.py'", workflow)
        self.assertIn("- 'src/test_final_pricing_release_gate.py'", workflow)


if __name__ == "__main__":
    unittest.main()

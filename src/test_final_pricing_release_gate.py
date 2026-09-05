import unittest
from datetime import date, timedelta
from pathlib import Path

from final_pricing_release_gate import is_release_grade_final, sanitize_payload


class FinalPricingReleaseGateTests(unittest.TestCase):
    def _final(self, **updates):
        filing = {
            "id": "priced-ipo",
            "company": "Acme Robotics, Inc.",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-08-24",
            "pricing_date": "2026-08-24",
            "offering_price": 18.0,
            "value": None,
            "filing_price": None,
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

    def test_final_prospectus_requires_positive_final_ipo_price(self):
        for value in (None, "", 0, -1, "unknown", float("nan"), True):
            with self.subTest(value=value):
                self.assertFalse(is_release_grade_final(self._final(offering_price=value)))

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

        payload, removed = sanitize_payload(
            {"schema_version": 1, "filings": [good, bad_stage, bad_date, bad_price]}
        )

        self.assertEqual([item["id"] for item in payload["filings"]], ["good"])
        self.assertEqual(
            [item["id"] for item in removed],
            ["bad-stage", "bad-date", "bad-price"],
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

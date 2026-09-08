import unittest

from final_pricing_release_gate import is_release_grade_final, sanitize_payload


class PrepricingLifecycleReleaseGateTests(unittest.TestCase):
    def _prepricing(self, **updates):
        filing = {
            "id": "prepricing",
            "company": "Acme Robotics, Inc.",
            "form": "S-1/A",
            "stage": "Pre-pricing",
            "filed": "2026-08-20",
            "pricing_date": None,
            "offering_price": None,
            "value": None,
        }
        filing.update(updates)
        return filing

    def test_clean_prepricing_registration_remains_release_safe(self):
        self.assertTrue(is_release_grade_final(self._prepricing()))

    def test_s1_stage_drift_fails_closed(self):
        for stage in ("Priced", "", None):
            with self.subTest(stage=stage):
                self.assertFalse(is_release_grade_final(self._prepricing(stage=stage)))

    def test_s1_cannot_carry_final_pricing_metadata(self):
        self.assertFalse(
            is_release_grade_final(self._prepricing(pricing_date="2026-08-24"))
        )
        self.assertFalse(is_release_grade_final(self._prepricing(offering_price=18.0)))

    def test_sanitizer_removes_only_impossible_prepricing_lifecycle_rows(self):
        good = self._prepricing(id="good")
        bad_stage = self._prepricing(id="bad-stage", stage="Priced")
        bad_date = self._prepricing(id="bad-date", pricing_date="2026-08-24")
        bad_price = self._prepricing(id="bad-price", offering_price=18.0)

        payload, removed = sanitize_payload(
            {"schema_version": 1, "filings": [good, bad_stage, bad_date, bad_price]}
        )

        self.assertEqual([item["id"] for item in payload["filings"]], ["good"])
        self.assertEqual(
            [item["id"] for item in removed],
            ["bad-stage", "bad-date", "bad-price"],
        )


if __name__ == "__main__":
    unittest.main()

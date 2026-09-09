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

    def test_s1_cannot_carry_live_quote_or_quote_provenance(self):
        self.assertFalse(is_release_grade_final(self._prepricing(current_price=22.5)))
        self.assertFalse(
            is_release_grade_final(
                self._prepricing(price_updated="2026-09-08T20:00:00+00:00")
            )
        )

    def test_s1_cannot_carry_quote_derived_person_values(self):
        for field, value in (
            ("cash_value", 1250000.0),
            ("liquid_value", 250000.0),
            ("locked_value", 1000000.0),
            ("valuation_as_of", "2026-09-08"),
        ):
            with self.subTest(field=field):
                self.assertFalse(
                    is_release_grade_final(
                        self._prepricing(people=[{"name": "Alex Holder", field: value}])
                    )
                )

    def test_s1_cannot_carry_market_value_signal_after_quote_is_removed(self):
        self.assertFalse(
            is_release_grade_final(
                self._prepricing(
                    signals=["Largest named holding currently valued at $12.5M"]
                )
            )
        )
        self.assertFalse(
            is_release_grade_final(
                self._prepricing(signals=["Current market value: $12.5M"])
            )
        )

    def test_sanitizer_removes_only_impossible_prepricing_lifecycle_rows(self):
        good = self._prepricing(id="good")
        bad_stage = self._prepricing(id="bad-stage", stage="Priced")
        bad_date = self._prepricing(id="bad-date", pricing_date="2026-08-24")
        bad_price = self._prepricing(id="bad-price", offering_price=18.0)
        bad_quote = self._prepricing(id="bad-quote", current_price=22.5)
        bad_quote_time = self._prepricing(
            id="bad-quote-time", price_updated="2026-09-08T20:00:00+00:00"
        )
        bad_person_value = self._prepricing(
            id="bad-person-value",
            people=[{"name": "Alex Holder", "cash_value": 1250000.0}],
        )
        bad_market_signal = self._prepricing(
            id="bad-market-signal",
            signals=["Largest named holding currently valued at $12.5M"],
        )

        payload, removed = sanitize_payload(
            {
                "schema_version": 1,
                "filings": [
                    good,
                    bad_stage,
                    bad_date,
                    bad_price,
                    bad_quote,
                    bad_quote_time,
                    bad_person_value,
                    bad_market_signal,
                ],
            }
        )

        self.assertEqual([item["id"] for item in payload["filings"]], ["good"])
        self.assertEqual(
            [item["id"] for item in removed],
            [
                "bad-stage",
                "bad-date",
                "bad-price",
                "bad-quote",
                "bad-quote-time",
                "bad-person-value",
                "bad-market-signal",
            ],
        )


if __name__ == "__main__":
    unittest.main()

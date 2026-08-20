import unittest
from datetime import date

from lockup_parser import extract_holder_lockup_info
import dashboard_export


class LockupTrancheParserTests(unittest.TestCase):
    def test_lyntris_four_explicit_tranches_are_structured(self):
        text = """
        IPO Lock-Up. We, our directors and executive officers, and holders of substantially all of our capital stock,
        including the selling stockholders, will agree not to sell, transfer, dispose of, pledge or hedge the covered shares:
        25% of the shares for 180 days, 25% of the shares for 360 days following the offering,
        25% of the shares for 540 days following the offering, and the remainder of the shares for 720 days following the offering.
        """
        info = extract_holder_lockup_info(text)
        by_days = {term["duration_value"]: term for term in info["terms"] if term["duration_unit"] == "days"}
        self.assertEqual(set(by_days), {180, 360, 540, 720})
        self.assertEqual([by_days[d]["tranche_percent"] for d in (180, 360, 540, 720)], [25.0, 25.0, 25.0, 25.0])
        self.assertEqual(by_days[720]["tranche_label"], "arithmetic_remainder")
        self.assertTrue(all("substantially_all_holders" in by_days[d]["scope_tags"] for d in by_days))
        self.assertTrue(info["structured"])

    def test_unrelated_periods_are_not_lockup_tranches(self):
        text = """
        Lock-Up Agreements. Our directors and executive officers will not transfer their Lock-Up Securities for 180 days.
        The selling stockholders granted the underwriters an over-allotment option for 30 days after this prospectus.
        Under Rule 144, affiliates may sell within any three-month period beginning 90 days after this prospectus.
        Section 203 restricts certain business combinations with an interested stockholder for three years following acquisition.
        """
        info = extract_holder_lockup_info(text)
        self.assertEqual([(t["duration_value"], t["duration_unit"]) for t in info["terms"]], [(180, "days")])


class TrancheLiquidityTests(unittest.TestCase):
    def _lockup(self):
        return {
            "terms": [
                {"duration_value": 180, "duration_unit": "days", "end_date": "2026-12-01", "scope_tags": ["substantially_all_holders"], "scope": "substantially all pre-IPO holders", "tranche_percent": 25.0, "covers_full_position": True},
                {"duration_value": 360, "duration_unit": "days", "end_date": "2027-06-01", "scope_tags": ["substantially_all_holders"], "scope": "substantially all pre-IPO holders", "tranche_percent": 25.0, "covers_full_position": True},
                {"duration_value": 540, "duration_unit": "days", "end_date": "2027-12-01", "scope_tags": ["substantially_all_holders"], "scope": "substantially all pre-IPO holders", "tranche_percent": 25.0, "covers_full_position": True},
                {"duration_value": 720, "duration_unit": "days", "end_date": "2028-06-01", "scope_tags": ["substantially_all_holders"], "scope": "substantially all pre-IPO holders", "tranche_percent": 25.0, "covers_full_position": True},
            ],
            "scope_tags": ["substantially_all_holders"],
            "text": "explicit four-tranche holder lock-up",
            "value": 180,
            "unit": "days",
            "end": "2026-12-01",
        }

    def test_before_first_release_all_post_ipo_shares_are_locked(self):
        result = dashboard_export._person_liquidity(
            1000, 100000, 20, self._lockup(), "Jane Holder", {"role": None}, {}, as_of_date="2026-10-01"
        )
        self.assertEqual(result["locked_shares"], 1000)
        self.assertEqual(result["liquid_shares"], 0)
        self.assertEqual(result["locked_value"], 100000)
        self.assertEqual(result["liquid_value"], 0)
        self.assertIn("100%", result["liquidity_status"])
        self.assertEqual(result["lockup_end_date"], "2028-06-01")

    def test_after_first_release_only_remaining_75_percent_is_locked(self):
        result = dashboard_export._person_liquidity(
            1000, 100000, 20, self._lockup(), "Jane Holder", {"role": None}, {}, as_of_date="2027-01-01"
        )
        self.assertEqual(result["locked_shares"], 750)
        self.assertEqual(result["liquid_shares"], 250)
        self.assertEqual(result["locked_value"], 75000)
        self.assertEqual(result["liquid_value"], 25000)
        self.assertIn("75%", result["liquidity_status"])

    def test_role_specific_subset_clause_does_not_lock_entire_position(self):
        lockup = {
            "terms": [{
                "duration_value": 180, "duration_unit": "days", "end_date": "2027-02-15",
                "scope_tags": ["directors", "executive_officers"], "scope": "directors, executive officers",
                "tranche_percent": None, "covers_full_position": False,
            }],
            "scope_tags": ["directors", "executive_officers"], "text": "Rule 701 shares are subject to lock-up",
            "value": 180, "unit": "days", "end": "2027-02-15",
        }
        result = dashboard_export._person_liquidity(
            1000, 100000, 20, lockup, "Jane Director", {"role": "Director"}, {}, as_of_date="2026-10-01"
        )
        self.assertIsNone(result["locked_shares"])
        self.assertIsNone(result["liquid_shares"])
        self.assertIn("quantity unresolved", result["liquidity_status"])


if __name__ == "__main__":
    unittest.main()

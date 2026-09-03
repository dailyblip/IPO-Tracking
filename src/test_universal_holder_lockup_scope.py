import unittest

import dashboard_export
from lockup_parser import extract_holder_lockup_info


class UniversalHolderLockupScopeTests(unittest.TestCase):
    def _attovia_style_lockup(self):
        text = """
        Lock-Up Agreements. We, our officers, directors and all of our stockholders
        have agreed with the underwriters that for a period of 180 days after the date
        of this prospectus, subject to certain exceptions, they will not offer, pledge,
        sell, contract to sell, or otherwise dispose of any shares of common stock.
        """
        info = extract_holder_lockup_info(text)
        for term in info["terms"]:
            term["end_date"] = "2027-01-31"
        return {
            "terms": info["terms"],
            "scope_tags": info["scope_tags"],
            "text": info["raw_text"],
            "value": info["duration_value"],
            "unit": info["duration_unit"],
            "end": "2027-01-31",
        }

    def test_explicit_all_stockholders_clause_applies_to_generic_beneficial_owner(self):
        lockup = self._attovia_style_lockup()
        self.assertIn("substantially_all_holders", lockup["scope_tags"])

        result = dashboard_export._person_liquidity(
            1000,
            100000,
            17,
            lockup,
            "Frazier Life Sciences XI, L.P.",
            {"role": None},
            {},
            as_of_date="2026-09-01",
        )

        self.assertEqual(result["liquidity_status"], "Lock-up applies — covered quantity unresolved")
        self.assertEqual(result["lockup_end_date"], "2027-01-31")
        self.assertEqual(len(result["lockup_schedule"]), 1)
        for field in ("liquid_shares", "liquid_value", "locked_shares", "locked_value"):
            self.assertIsNone(result[field])

    def test_all_security_holders_wording_is_recognized(self):
        info = extract_holder_lockup_info(
            "All of our security holders have entered into lock-up agreements under which "
            "they have agreed not to sell any of our stock for 180 days following the date "
            "of this prospectus."
        )
        self.assertEqual(info["duration_value"], 180)
        self.assertIn("substantially_all_holders", info["scope_tags"])

    def test_officer_director_only_clause_remains_fail_closed_for_fund_holder(self):
        info = extract_holder_lockup_info(
            "Lock-Up Agreements. Our officers and directors have agreed not to sell or "
            "transfer their shares for 180 days following the date of this prospectus."
        )
        for term in info["terms"]:
            term["end_date"] = "2027-01-31"
        lockup = {
            "terms": info["terms"],
            "scope_tags": info["scope_tags"],
            "text": info["raw_text"],
            "value": info["duration_value"],
            "unit": info["duration_unit"],
            "end": "2027-01-31",
        }
        result = dashboard_export._person_liquidity(
            1000,
            100000,
            17,
            lockup,
            "Example Fund, L.P.",
            {"role": None},
            {},
            as_of_date="2026-09-01",
        )
        self.assertEqual(result["liquidity_status"], "Unclassified")
        self.assertEqual(result["lockup_schedule"], [])
        self.assertIsNone(result["locked_shares"])
        self.assertIsNone(result["liquid_shares"])


if __name__ == "__main__":
    unittest.main()

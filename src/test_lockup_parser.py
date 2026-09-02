import unittest
from lockup_parser import extract_holder_lockup_info


class LockupParserResearchGradeTests(unittest.TestCase):
    def test_neutron_prefers_160_day_holder_lockup_over_registration_rights_180_days(self):
        text = """
        Registration Rights. At any time beginning 180 days after the effective date, holders may request Form S-1 registration.
        Lock-Up and Market Standoff Agreements. We and all of our directors, executive officers, the selling stockholders,
        and certain other record holders are subject to lock-up agreements with the underwriters and will not transfer
        Lock-Up Securities during the period ending on 160 days after the date of this prospectus (the Lock-Up Period).
        """
        info = extract_holder_lockup_info(text)
        self.assertEqual(info["duration_value"], 160)
        self.assertEqual(info["duration_unit"], "days")
        self.assertIn("directors", info["scope_tags"])
        self.assertIn("selling_stockholders", info["scope_tags"])

    def test_space_x_keeps_founder_schedule_separate_from_general_lockup(self):
        text = """
        LOCK-UP PERIOD (i) 366-day lock-up for Elon Musk; (ii) staggered lock-up release for a portion of shares held by
        select investors, officers, and directors starting after Q4 26 earnings through Q2 27 earnings; and
        (iii) staggered early lock-up release for all other shares starting after Q2 26 earnings through 180 days after the IPO date.
        """
        info = extract_holder_lockup_info(text)
        self.assertTrue(info["structured"])
        self.assertEqual(info["duration_value"], 180)
        self.assertTrue(any(t.get("special_holder") == "Elon Musk" and t["duration_value"] == 366 for t in info["terms"]))

    def test_holder_six_month_term_beats_issuer_only_90_day_term(self):
        text = """
        Lock-Up Agreements. We have agreed for a period of 90 days after the offering not to issue additional securities.
        Furthermore, each of our directors and executive officers and all holders of 5% or more of our shares have agreed,
        subject to certain exceptions, not to dispose of their shares for a period of six (6) months after this offering is completed
        without the prior written consent of the underwriter.
        """
        info = extract_holder_lockup_info(text)
        self.assertEqual(info["duration_value"], 6)
        self.assertEqual(info["duration_unit"], "months")
        self.assertIn("directors", info["scope_tags"])

    def test_lyntris_discards_greenshoe_rule144_and_dgcl_periods(self):
        text = """
        However, any shares issued under Rule 701 to our executive officers and directors are subject to lock-up agreements
        and will only become eligible for sale when the 180-day lock-up agreements expire.
        Underwriters' option to purchase additional shares. The selling stockholders have granted the underwriters an option
        to purchase additional shares for 30 days after the date of this prospectus.
        In general, under Rule 144, affiliates may sell after expiration of the lock-up agreements, within any three-month period
        beginning 90 days after the date of this prospectus.
        Business Combinations. Section 203 prohibits certain business combinations with an interested stockholder for a period
        of three years following the time such stockholder became interested.
        """
        info = extract_holder_lockup_info(text)
        self.assertEqual(info["duration_value"], 180)
        self.assertEqual(info["duration_unit"], "days")
        self.assertEqual([(t["duration_value"], t["duration_unit"]) for t in info["terms"]], [(180, "days")])

    def test_reformation_accepts_explicit_restrict_the_sale_lockup_clause(self):
        text = """
        We, all of our directors, executive officers and the holders of substantially all of our outstanding securities,
        including the selling stockholders and the stockholders participating in the Synthetic Secondary, are subject to
        lock-up agreements with the underwriters that will, subject to certain customary exceptions, restrict the sale of
        the shares of our common stock and certain other securities held by them for up to 180 days following the date of this prospectus.
        """
        info = extract_holder_lockup_info(text)
        self.assertEqual(info["duration_value"], 180)
        self.assertEqual(info["duration_unit"], "days")
        self.assertEqual(info["confidence"], "High")
        self.assertIn("substantially_all_holders", info["scope_tags"])
        self.assertIn("directors", info["scope_tags"])
        self.assertIn("executive_officers", info["scope_tags"])
        self.assertIn("selling_stockholders", info["scope_tags"])

    def test_no_lockup_language_stays_unresolved(self):
        info = extract_holder_lockup_info("This prospectus discusses revenue and customers only.")
        self.assertIsNone(info["duration_value"])
        self.assertEqual(info["terms"], [])

if __name__ == "__main__":
    unittest.main()

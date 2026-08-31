import unittest
from prospect_research import confirmed_boolean, holder_type, prospect_person_metadata

class ProspectResearchTests(unittest.TestCase):
    def test_holder_type_distinguishes_people_from_entities(self):
        self.assertEqual(holder_type("Jane Smith"), "Individual")
        self.assertEqual(holder_type("Example Ventures LP"), "Fund")
        self.assertEqual(holder_type("Smith Family Trust"), "Trust")

    def test_affiliate_owner_rows_are_not_misclassified_as_people(self):
        self.assertEqual(holder_type("Entities affiliated with Westlake BioPartners"), "Entity")
        self.assertEqual(holder_type("Entities affiliated with Foresite Capital"), "Entity")
        self.assertEqual(holder_type("Funds affiliated with Example Ventures"), "Entity")
        self.assertEqual(holder_type("Affiliates of Example Holdings LLC"), "Entity")

    def test_metadata_preserves_only_available_research_facts(self):
        row={"Title":"CEO", "Percent Ownership":"12.4%", "Shares":"100", "Stanford Justification":"Stanford bio"}
        m=prospect_person_metadata(row,"Jane Smith")
        self.assertEqual(m["role"],"CEO")
        self.assertEqual(m["ownership_percent"],"12.4%")
        self.assertEqual(m["shares_after_ipo"],"100")
        self.assertEqual(m["stanford_source"],"Stanford bio")

    def test_metadata_fails_closed_on_impossible_ownership_metrics(self):
        row = {
            "Ownership % Before IPO": 25_313_314,
            "Ownership % After IPO": 17.0,
            "Shares Before IPO": 18.2,
            "Shares After IPO": 25_313_314,
            "Shares Sold in IPO": -1,
        }
        m = prospect_person_metadata(row, "Entities affiliated with Example Capital")
        self.assertIsNone(m["ownership_percent_before"])
        self.assertEqual(m["ownership_percent_after"], 17.0)
        self.assertEqual(m["ownership_percent"], 17.0)
        self.assertIsNone(m["shares_before_ipo"])
        self.assertEqual(m["shares_after_ipo"], 25_313_314)
        self.assertIsNone(m["shares_sold_ipo"])

    def test_metadata_rejects_nonfinite_and_out_of_range_metrics(self):
        for percent in (-0.1, 100.1, float("nan"), float("inf")):
            with self.subTest(percent=percent):
                m = prospect_person_metadata({"Ownership % After IPO": percent}, "Jane Smith")
                self.assertIsNone(m["ownership_percent"])
                self.assertIsNone(m["ownership_percent_after"])
        for shares in (-1, 1.5, float("nan"), float("inf")):
            with self.subTest(shares=shares):
                m = prospect_person_metadata({"Shares After IPO": shares}, "Jane Smith")
                self.assertIsNone(m["shares_after_ipo"])

    def test_confirmed_boolean_rejects_false_like_strings(self):
        for value in (False, None, "", "false", "False", "no", "0", 0):
            self.assertFalse(confirmed_boolean(value), value)
        for value in (True, "true", "TRUE", "yes", "Y", "1", 1):
            self.assertTrue(confirmed_boolean(value), value)

    def test_stanford_affiliation_requires_explicit_affirmative_value_and_grade_five(self):
        for value in ("False", "No", "0"):
            m=prospect_person_metadata({
                "Stanford Affiliation Confirmed": value,
                "Stanford Grade": 5,
            }, "Jane Smith")
            self.assertFalse(m["stanford_affiliation_confirmed"], value)
            self.assertFalse(m["stanford_university_bio"], value)

        for grade in (None, 0, 1, 2, 3, 4):
            m=prospect_person_metadata({
                "Stanford Affiliation Confirmed": "Yes",
                "Stanford Grade": grade,
            }, "Jane Smith")
            self.assertFalse(m["stanford_affiliation_confirmed"], grade)
            self.assertFalse(m["stanford_university_bio"], grade)

        m=prospect_person_metadata({
            "Stanford Affiliation Confirmed": "Yes",
            "Stanford Grade": 5,
        }, "Jane Smith")
        self.assertTrue(m["stanford_affiliation_confirmed"])
        self.assertTrue(m["stanford_university_bio"])

    def test_confirmed_affiliation_overrides_legacy_bio_flag_for_ui(self):
        m=prospect_person_metadata({
            "Stanford Affiliation Confirmed": "No",
            "Stanford University in Bio": "Yes",
            "Stanford Grade": 5,
        }, "Jane Smith")
        self.assertFalse(m["stanford_affiliation_confirmed"])
        self.assertFalse(m["stanford_university_bio"])

    def test_legacy_bio_flag_also_requires_grade_five(self):
        unconfirmed = prospect_person_metadata({
            "Stanford University in Bio": "Yes",
            "Stanford Grade": 4,
        }, "Jane Smith")
        self.assertFalse(unconfirmed["stanford_affiliation_confirmed"])

        confirmed = prospect_person_metadata({
            "Stanford University in Bio": "Yes",
            "Stanford Grade": 5,
        }, "Jane Smith")
        self.assertTrue(confirmed["stanford_affiliation_confirmed"])

if __name__ == "__main__": unittest.main()

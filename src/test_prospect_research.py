import unittest
from prospect_research import confirmed_boolean, holder_type, prospect_person_metadata

class ProspectResearchTests(unittest.TestCase):
    def test_holder_type_distinguishes_people_from_entities(self):
        self.assertEqual(holder_type("Jane Smith"), "Individual")
        self.assertEqual(holder_type("Example Ventures LP"), "Fund")
        self.assertEqual(holder_type("Smith Family Trust"), "Trust")

    def test_metadata_preserves_only_available_research_facts(self):
        row={"Title":"CEO", "Percent Ownership":"12.4%", "Shares":"100", "Stanford Justification":"Stanford bio"}
        m=prospect_person_metadata(row,"Jane Smith")
        self.assertEqual(m["role"],"CEO")
        self.assertEqual(m["ownership_percent"],"12.4%")
        self.assertEqual(m["shares_after_ipo"],"100")
        self.assertEqual(m["stanford_source"],"Stanford bio")

    def test_confirmed_boolean_rejects_false_like_strings(self):
        for value in (False, None, "", "false", "False", "no", "0", 0):
            self.assertFalse(confirmed_boolean(value), value)
        for value in (True, "true", "TRUE", "yes", "Y", "1", 1):
            self.assertTrue(confirmed_boolean(value), value)

    def test_stanford_affiliation_requires_explicit_affirmative_value(self):
        for value in ("False", "No", "0"):
            m=prospect_person_metadata({"Stanford Affiliation Confirmed": value}, "Jane Smith")
            self.assertFalse(m["stanford_affiliation_confirmed"], value)
            self.assertFalse(m["stanford_university_bio"], value)
        m=prospect_person_metadata({"Stanford Affiliation Confirmed": "Yes"}, "Jane Smith")
        self.assertTrue(m["stanford_affiliation_confirmed"])
        self.assertTrue(m["stanford_university_bio"])

    def test_confirmed_affiliation_overrides_legacy_bio_flag_for_ui(self):
        m=prospect_person_metadata({
            "Stanford Affiliation Confirmed": "No",
            "Stanford University in Bio": "Yes",
        }, "Jane Smith")
        self.assertFalse(m["stanford_affiliation_confirmed"])
        self.assertFalse(m["stanford_university_bio"])

if __name__ == "__main__": unittest.main()

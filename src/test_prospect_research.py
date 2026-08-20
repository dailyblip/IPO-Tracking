import unittest
from prospect_research import holder_type, prospect_person_metadata

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

if __name__ == "__main__": unittest.main()

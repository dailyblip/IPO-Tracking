import unittest

from prospect_research import holder_type


class InstitutionalHolderTypeTests(unittest.TestCase):
    def test_sovereign_and_public_institutions_are_not_people(self):
        self.assertEqual(holder_type("Abu Dhabi Investment Authority"), "Entity")
        self.assertEqual(holder_type("University of California"), "Entity")
        self.assertEqual(holder_type("California State Teachers Retirement System"), "Entity")
        self.assertEqual(holder_type("Example Pension Board"), "Entity")

    def test_corporate_company_names_are_not_people(self):
        self.assertEqual(holder_type("Eli Lilly and Company"), "Entity")
        self.assertEqual(holder_type("The Boeing Company"), "Entity")
        self.assertEqual(holder_type("Akastor ASA"), "Entity")
        self.assertEqual(holder_type("Example GmbH"), "Entity")

    def test_plural_fund_labels_are_not_people(self):
        self.assertEqual(holder_type("MDP Funds"), "Fund")
        self.assertEqual(holder_type("Example Healthcare Funds"), "Fund")

    def test_role_labeled_natural_people_are_not_misclassified_as_entities(self):
        self.assertEqual(
            holder_type("Scott W. Knoll, EVP, Corporate Strategy and Director"),
            "Individual",
        )
        self.assertEqual(
            holder_type("Travis Murdoch, M.D., Chief Executive Officer, President and Director"),
            "Individual",
        )

    def test_normal_person_name_remains_individual(self):
        self.assertEqual(holder_type("Jane Smith"), "Individual")


if __name__ == "__main__":
    unittest.main()

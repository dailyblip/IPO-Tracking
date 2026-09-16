import unittest

from prospect_research import holder_type


class MutualHoldingCompanyHolderTypeRegressionTests(unittest.TestCase):
    def test_mhc_owner_is_entity(self):
        self.assertEqual(holder_type("Mutual Federal, MHC"), "Entity")

    def test_spelled_out_mutual_holding_company_is_entity(self):
        self.assertEqual(holder_type("Example Mutual Holding Company"), "Entity")


if __name__ == "__main__":
    unittest.main()

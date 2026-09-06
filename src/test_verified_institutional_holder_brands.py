import unittest

from prospect_research import holder_type


class VerifiedInstitutionalHolderBrandTests(unittest.TestCase):
    def test_sec_verified_standalone_corporate_brands_are_entities(self):
        self.assertEqual(holder_type("American Securities"), "Entity")
        self.assertEqual(holder_type("Brookfield"), "Entity")
        self.assertEqual(holder_type("Uber"), "Entity")

    def test_ambiguous_single_token_still_fails_closed(self):
        self.assertEqual(holder_type("Kedge"), "Unknown")


if __name__ == "__main__":
    unittest.main()

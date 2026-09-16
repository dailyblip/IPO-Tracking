import unittest

from prospect_research import holder_type


class DutchCooperativeAdjectivalHolderTests(unittest.TestCase):
    def test_dutch_cooperative_adjectival_legal_forms_are_entities(self):
        self.assertEqual(
            holder_type("Coöperatieve Gilde Healthcare VG VI U.A."),
            "Entity",
        )
        self.assertEqual(
            holder_type("Example Cooperatieve Holding U.A."),
            "Entity",
        )


if __name__ == "__main__":
    unittest.main()

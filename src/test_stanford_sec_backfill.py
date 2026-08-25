import unittest

from stanford_sec_backfill import find_sec_stanford_affiliation


class StanfordSecBackfillTests(unittest.TestCase):
    def test_confirms_exact_beneficial_owner_from_management_bio(self):
        text = (
            "MANAGEMENT Executive Officers and Directors Wayne Ting 42 Chief Executive Officer "
            "Joseph Kraus 54 President Ann Gugino 53 Chief Financial Officer. "
            "Wayne Ting has served as our Chief Executive Officer since May 2020. "
            "Joseph Kraus has served as our President since November 2018. "
            "Mr. Kraus holds a B.A. in Political Science from Stanford University. "
            "Ann Gugino has served as our Chief Financial Officer since December 2023."
        )
        self.assertTrue(
            find_sec_stanford_affiliation(
                text,
                "Joseph Kraus(2)",
                ["Wayne Ting", "Joseph Kraus(2)", "Ann Gugino"],
            )
        )

    def test_does_not_assign_neighboring_persons_stanford_credential(self):
        text = (
            "Wayne Ting has served as our Chief Executive Officer since May 2020. "
            "Joseph Kraus has served as our President since November 2018. "
            "Mr. Kraus holds a B.A. in Political Science from Stanford University."
        )
        self.assertFalse(
            find_sec_stanford_affiliation(
                text,
                "Wayne Ting",
                ["Wayne Ting", "Joseph Kraus"],
            )
        )

    def test_requires_explicit_affiliation_language(self):
        text = (
            "Joseph Kraus has served as our President since November 2018. "
            "The company participates in programs near Stanford University."
        )
        self.assertFalse(find_sec_stanford_affiliation(text, "Joseph Kraus", ["Joseph Kraus"]))

    def test_requires_full_person_name(self):
        text = "Mr. Kraus holds a B.A. in Political Science from Stanford University."
        self.assertFalse(find_sec_stanford_affiliation(text, "Joseph Kraus", ["Joseph Kraus"]))


if __name__ == "__main__":
    unittest.main()

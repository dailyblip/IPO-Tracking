import unittest

from prospect_research import prospect_person_metadata


class HolderRoleFallbackTests(unittest.TestCase):
    def test_explicit_role_suffix_is_preserved_when_role_column_is_blank(self):
        metadata = prospect_person_metadata(
            {},
            "Tassos Gianakakos, Chief Executive Officer, Director, and Chair",
        )
        self.assertEqual(
            metadata["role"],
            "Chief Executive Officer, Director, and Chair",
        )

    def test_professional_credentials_are_not_folded_into_role(self):
        metadata = prospect_person_metadata(
            {},
            "Jay Edelberg, M.D., Ph.D., Chief Medical Officer",
        )
        self.assertEqual(metadata["role"], "Chief Medical Officer")

    def test_structured_role_remains_authoritative(self):
        metadata = prospect_person_metadata(
            {"Role": "Chief Scientific Officer"},
            "Jane Smith, Director",
        )
        self.assertEqual(metadata["role"], "Chief Scientific Officer")

    def test_entity_label_does_not_generate_person_role(self):
        metadata = prospect_person_metadata({}, "Example Capital, L.P.")
        self.assertIsNone(metadata["role"])


if __name__ == "__main__":
    unittest.main()

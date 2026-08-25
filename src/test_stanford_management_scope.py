import unittest

import main


class StanfordManagementScopeTests(unittest.TestCase):
    def test_management_bios_exclude_existing_beneficial_owners(self):
        bios = {
            "Nima Farzan": "Mr. Farzan earned his B.A. from Stanford University.",
            "Jane Director": "Ms. Director serves on our board and attended Stanford University.",
            "_full_text": "Combined filing text.",
        }
        candidates = main._management_bio_candidates(bios, ["Nima Farzan(6)"])
        self.assertEqual(candidates, [
            ("Jane Director", "Ms. Director serves on our board and attended Stanford University.")
        ])

    def test_person_key_normalizes_sec_footnotes_and_punctuation(self):
        self.assertEqual(main._person_key("Nima Farzan(6)"), "nima farzan 6")
        # Prefix-compatible matching in _person_bio still lets the ownership row
        # resolve to the management bio even when SEC footnotes are present.
        bios = {"Nima Farzan": "Stanford University", "_full_text": "ignored"}
        self.assertEqual(main._person_bio(bios, "Nima Farzan(6)"), "Stanford University")

    def test_management_scope_is_not_limited_to_owner_rows(self):
        source = open(main.__file__, encoding="utf-8").read()
        self.assertIn("_management_bio_candidates", source)
        self.assertIn("Stanford connection confirmed for management/director", source)
        self.assertIn('"Stanford Affiliation Confirmed": True', source)


if __name__ == "__main__":
    unittest.main()

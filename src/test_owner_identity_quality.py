import unittest

from ownership_parser import looks_like_document_heading


class OwnerIdentityQualityTests(unittest.TestCase):
    def test_live_document_headings_are_not_owner_identities(self):
        headings = (
            "Forward-Looking Statements",
            "A Letter From Our CEO",
            "Business",
            "CERTAIN RELATIONSHIPS AND RELATED PERSON TRANSACTIONS",
        )
        for heading in headings:
            with self.subTest(heading=heading):
                self.assertTrue(looks_like_document_heading(heading))

    def test_heading_rules_do_not_reject_legitimate_entity_names(self):
        self.assertFalse(looks_like_document_heading("Business Development Partners LLC"))
        self.assertFalse(looks_like_document_heading("Forward Looking Capital LLC"))


if __name__ == "__main__":
    unittest.main()

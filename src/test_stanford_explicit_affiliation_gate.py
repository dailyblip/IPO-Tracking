import unittest
from unittest.mock import patch

import stanford_grader


class StanfordExplicitAffiliationGateTests(unittest.TestCase):
    def test_incidental_stanford_university_mention_does_not_auto_confirm(self):
        fallback = {
            "grade": 0,
            "justification": "No person-level Stanford affiliation found.",
            "source": "openai_web_research",
            "source_url": "",
        }
        bio = (
            "Jane Doe is Chief Executive Officer of Acme. "
            "Acme collaborates with Stanford University on a company-sponsored study."
        )
        with patch.object(
            stanford_grader, "grade_via_llm", return_value=fallback
        ) as llm:
            result = stanford_grader.grade_stanford_affiliation(
                "Jane Doe", "Acme", "CEO", bio
            )

        self.assertEqual(result["grade"], 0)
        llm.assert_called_once()

    def test_degree_abbreviation_remains_direct_grade_five_evidence(self):
        bio = "Jane Doe received her B.A. from Stanford University."
        with patch.object(stanford_grader, "grade_via_llm") as llm:
            result = stanford_grader.grade_stanford_affiliation(
                "Jane Doe", "Acme", "CEO", bio
            )

        self.assertEqual(result["grade"], 5)
        self.assertEqual(result["source"], "filing_bio")
        self.assertIn("Stanford University", result["justification"])
        llm.assert_not_called()

    def test_customer_or_partner_reference_is_not_direct_affiliation(self):
        for bio in (
            "Jane Doe serves customers including Stanford University.",
            "Jane Doe leads Acme's partnership with Stanford University.",
        ):
            with self.subTest(bio=bio):
                self.assertIsNone(
                    stanford_grader.check_bio_for_stanford(
                        bio, person_name="Jane Doe"
                    )
                )


if __name__ == "__main__":
    unittest.main()

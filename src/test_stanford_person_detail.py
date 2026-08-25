import unittest
from pathlib import Path

from prospect_research import prospect_person_metadata


class StanfordPersonDetailTests(unittest.TestCase):
    def test_public_source_carries_one_to_five_confidence_without_confirming_leads(self):
        metadata = prospect_person_metadata({
            "Stanford Grade": 4,
            "Stanford Justification": "Official company bio says he attended Stanford, but degree details are unclear.",
            "Stanford Affiliation Confirmed": False,
        }, "Jordan Example")
        self.assertEqual(
            metadata["stanford_source"],
            "Confidence 4/5 — Official company bio says he attended Stanford, but degree details are unclear.",
        )
        self.assertFalse(metadata["stanford_university_bio"])

    def test_confirmed_affiliation_remains_the_only_red_text_gate(self):
        metadata = prospect_person_metadata({
            "Stanford Grade": 5,
            "Stanford Justification": "MBA, Stanford Graduate School of Business; confirmed by issuer biography.",
            "Stanford Affiliation Confirmed": True,
        }, "Jordan Example")
        self.assertEqual(
            metadata["stanford_source"],
            "Confidence 5/5 — MBA, Stanford Graduate School of Business; confirmed by issuer biography.",
        )
        self.assertTrue(metadata["stanford_university_bio"])

    def test_ui_removes_s_badge_and_adds_person_connection_panel(self):
        html = (Path(__file__).resolve().parents[1] / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("stanfordBadge", html)
        self.assertNotIn("stanford-s", html)
        self.assertIn('id="personStanford"', html)
        self.assertIn('id="personStanfordConfidence"', html)
        self.assertIn('id="personStanfordNote"', html)
        self.assertIn("Confidence ${research.confidence}/5", html)
        self.assertIn("person.stanford_university_bio===true&&Number.isFinite(shares)&&shares>0", html)


if __name__ == "__main__":
    unittest.main()

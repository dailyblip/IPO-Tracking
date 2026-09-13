import unittest
from pathlib import Path


HTML = Path(__file__).resolve().parents[1] / "docs" / "index.html"


class StanfordConfidenceUiContractTests(unittest.TestCase):
    def test_unscored_confirmed_affiliation_does_not_invent_confidence(self):
        html = HTML.read_text(encoding="utf-8")

        self.assertIn(
            'if(person.stanford_university_bio===true)return{confidence:null,note:raw||"Confirmed Stanford affiliation; source detail is not available in this historical record."}',
            html,
        )
        self.assertNotIn(
            'if(person.stanford_university_bio===true)return{confidence:5',
            html,
        )
        self.assertIn('if(research.confidence!==null)', html)

    def test_evidence_supported_confidence_remains_visible(self):
        html = HTML.read_text(encoding="utf-8")

        self.assertIn(
            'match=raw.match(/^Confidence\\s+([1-5])\\/5\\s+—\\s+(.+)$/s)',
            html,
        )
        self.assertIn('return{confidence:Number(match[1]),note:match[2].trim()}', html)
        self.assertIn('`Confidence ${research.confidence}/5`', html)


if __name__ == "__main__":
    unittest.main()

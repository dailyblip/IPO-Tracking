import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs" / "index.html"
PROSPECT_HTML = ROOT / "docs" / "prospect-research" / "index.html"


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

    def test_prospect_liquidity_does_not_invent_stanford_confidence(self):
        html = PROSPECT_HTML.read_text(encoding="utf-8")

        self.assertIn('confidence=match?Number(match[1]):null', html)
        self.assertNotIn('confidence=match?Number(match[1]):(hasStanfordResearch(p)?5:null)', html)
        self.assertNotIn('id="stanfordConfidence">Confidence 5/5', html)
        self.assertIn('research.confidence?`Confidence ${research.confidence}/5`:"Research lead"', html)


if __name__ == "__main__":
    unittest.main()

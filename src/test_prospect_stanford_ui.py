import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs" / "prospect-research" / "index.html"


class ProspectStanfordUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")

    def test_cardinal_text_is_the_only_stanford_visual_marker(self):
        self.assertNotIn('.badge.stanford', self.html)
        self.assertNotIn('badge("Stanford","stanford")', self.html)
        self.assertNotIn('badge("Confirmed Stanford-affiliated beneficial owner","stanford")', self.html)
        self.assertIn('d.className=hasStanford(f)?"company cardinal":"company"', self.html)
        self.assertIn('b.className="owner-link"+(isStanfordPerson(p)?" cardinal":"")', self.html)
        self.assertIn('$("personName").className=isStanfordPerson(p)?"cardinal":""', self.html)

    def test_person_record_shows_stanford_note_and_one_to_five_confidence(self):
        self.assertIn('id="stanfordPerson"', self.html)
        self.assertIn('Stanford Connection', self.html)
        self.assertIn('id="stanfordConfidence"', self.html)
        self.assertIn('function stanfordResearchFor(p)', self.html)
        self.assertIn('raw.match(/^Confidence\\s+([1-5])\\/5', self.html)
        self.assertIn('`Confidence ${research.confidence}/5`', self.html)
        self.assertIn('$("stanfordSource").textContent=research.note', self.html)

    def test_unconfirmed_research_can_display_without_triggering_red(self):
        self.assertIn('confidence=match?Number(match[1]):(isStanfordPerson(p)?5:null)', self.html)
        self.assertIn('sp.hidden=research.confidence===null&&!research.note', self.html)
        self.assertIn('function isStanfordPerson(p){return p?.stanford_affiliation_confirmed===true||p?.stanford_university_bio===true||stanfordOverrides.has', self.html)

    def test_company_red_requires_confirmed_owner_with_disclosed_shares(self):
        self.assertIn('function hasStanford(f){return (f.people||[]).some(p=>isStanfordPerson(p)&&Number(p.shares_after_ipo??p.shares)>0)}', self.html)


if __name__ == "__main__":
    unittest.main()

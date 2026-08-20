import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs" / "prospect-research" / "index.html"
BACKFILL_PATH = ROOT / "docs" / "prospect-research" / "backfill.json"


class ProspectLiquiditySiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.backfill = json.loads(BACKFILL_PATH.read_text(encoding="utf-8"))

    def test_homepage_is_company_first(self):
        for label in (
            "Company",
            "Ticker",
            "Stage",
            "IPO size / offering value",
            "Final IPO price",
            "Current price",
            "Beneficial owners",
            "Lock-up end",
        ):
            self.assertIn(label, self.html)
        self.assertIn('className="company-row"', self.html)
        self.assertNotIn('<th>Person / Owner</th><th>Company</th>', self.html)

    def test_company_detail_contains_beneficial_ownership_grid(self):
        self.assertIn('id="companyDetail"', self.html)
        self.assertIn("Beneficial ownership", self.html)
        self.assertIn('id="ownerRows"', self.html)
        self.assertIn('className="owner-link"', self.html)

    def test_person_liquidity_profile_is_drilldown_only(self):
        self.assertIn('id="personDetail"', self.html)
        for label in (
            "Current holding value",
            "Liquid now",
            "Locked / restricted",
            "IPO-date value of holding",
            "Cash actually realized in IPO",
            "Classification confidence",
        ):
            self.assertIn(label, self.html)
        self.assertIn('showPerson((selectedCompany.people||[])[Number(b.dataset.person)])', self.html)
        self.assertIn('personDetail.showModal()', self.html)

    def test_liquidity_visual_distinguishes_unknown_from_locked(self):
        self.assertIn('segment("liquid"', self.html)
        self.assertIn('segment("locked"', self.html)
        self.assertIn('segment("unknown"', self.html)
        self.assertIn("Unknown / unclassified", self.html)

    def test_does_not_equate_paper_value_with_realized_cash(self):
        self.assertIn("Paper value of disclosed shares", self.html)
        self.assertIn("Secondary-sale proceeds", self.html)
        self.assertIn("not cash already received", self.html)

    def test_site_uses_existing_public_feed_without_changing_root_monitor(self):
        self.assertIn('fetch("../data/filings.json"', self.html)
        self.assertIn('fetch("backfill.json"', self.html)
        self.assertIn("Open SEC Research Monitor", self.html)

    def test_flags_500m_plus_ipos(self):
        self.assertIn("$500M+ IPOs", self.html)
        self.assertIn('Number(f.ipo_size||f.value||0)>=500000000', self.html)
        self.assertIn('badge("IPO $500M+","major")', self.html)

    def test_restores_stanford_affiliation_signals(self):
        self.assertIn('badge("Stanford","stanford")', self.html)
        self.assertIn("Stanford affiliation", self.html)
        names = {row["name"] for row in self.backfill["stanford_overrides"]}
        self.assertIn("Steve Jurvetson", names)
        self.assertIn("Ira Ehrenpreis", names)

    def test_backfills_neutron_and_bending_spoons(self):
        companies = {row["company"]: row for row in self.backfill["filings"]}
        self.assertEqual(companies["Neutron Holdings, Inc."]["ticker"], "LIME")
        self.assertEqual(companies["Neutron Holdings, Inc."]["ipo_size"], 173_913_050)
        self.assertEqual(companies["Bending Spoons S.p.A."]["ticker"], "BSP")
        self.assertEqual(companies["Bending Spoons S.p.A."]["ipo_size"], 1_681_159_435)
        self.assertGreater(companies["Neutron Holdings, Inc."]["people"][0]["shares"], 0)

    def test_researcher_workflow_fields_and_filters(self):
        for label in ("Stanford-linked IPOs", "Lock-ups ≤90 days", "$500M+ IPO", "Selling shareholders", "Type", "Role", "% ownership", "Ownership transition", "Estimated IPO liquidity event", "Current valuation date not available"):
            self.assertIn(label, self.html)
        self.assertIn('id="researchFilter"', self.html)
        self.assertIn('p.holder_type||"Unknown"', self.html)
        self.assertIn('Entity record — no individual prospect profile', self.html)


if __name__ == "__main__":
    unittest.main()

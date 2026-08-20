import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs" / "prospect-research" / "index.html"


class ProspectLiquiditySiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")

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
        self.assertIn("Open SEC Research Monitor", self.html)


if __name__ == "__main__":
    unittest.main()

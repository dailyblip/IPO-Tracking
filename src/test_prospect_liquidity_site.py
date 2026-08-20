import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs" / "prospect-research" / "index.html"


class ProspectLiquiditySiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")

    def test_person_centric_liquidity_fields_are_present(self):
        for label in (
            "Current holding value",
            "Liquid now",
            "Locked / restricted",
            "IPO-date value of holding",
            "Cash actually realized in IPO",
            "Lock-up",
            "Classification confidence",
        ):
            self.assertIn(label, self.html)

    def test_liquidity_visual_distinguishes_unknown_from_locked(self):
        self.assertIn('segment("liquid"', self.html)
        self.assertIn('segment("locked"', self.html)
        self.assertIn('segment("unknown"', self.html)
        self.assertIn("Unclassified / not enough disclosure", self.html)

    def test_site_uses_existing_public_feed_without_changing_root_monitor(self):
        self.assertIn('fetch("../data/filings.json"', self.html)
        self.assertIn("Open SEC Research Monitor", self.html)

    def test_person_rows_are_clickable(self):
        self.assertIn('rows.addEventListener("click"', self.html)
        self.assertIn('detail.showModal()', self.html)

    def test_does_not_equate_paper_value_with_realized_cash(self):
        self.assertIn("not simply paper value", self.html)
        self.assertIn("not the same as cash already received", self.html)


if __name__ == "__main__":
    unittest.main()

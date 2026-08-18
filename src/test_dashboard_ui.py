import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs" / "index.html"
FEED_PATH = ROOT / "docs" / "data" / "filings.json"


class DashboardUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.feed = json.loads(FEED_PATH.read_text(encoding="utf-8"))

    def test_has_functional_workflow_controls(self):
        for element_id in (
            "queueView", "savedView", "search", "formFilter", "priorityFilter",
            "statusFilter", "dateFilter", "sortBy", "clearFilters", "resultCount",
            "detailFilingPrice", "detailIpoPrice", "detailCurrentPrice",
            "detailPriceUpdated", "startReview", "markReview", "toggleSaved",
            "openSec", "reload",
        ):
            self.assertIn(f'id="{element_id}"', self.html)

    def test_queue_supports_researcher_filtering_and_sorting(self):
        self.assertIn("function populateFormFilter()", self.html)
        self.assertIn("function dateWithin(filed,days)", self.html)
        self.assertIn('sort==="value-desc"', self.html)
        self.assertIn('sort==="owners-desc"', self.html)
        self.assertIn("function clearFilters()", self.html)
        self.assertIn("Last 30 days", self.html)

    def test_displays_all_requested_price_fields(self):
        self.assertIn("IPO size</th>", self.html)
        self.assertIn("Offering value</th>", self.html)
        self.assertIn("money(filing.ipo_size)", self.html)
        self.assertIn("money(filing.value)", self.html)
        self.assertIn("Filing price</th>", self.html)
        self.assertIn("Final IPO price</th>", self.html)
        self.assertIn("Current price</th>", self.html)
        self.assertIn("filing.price_range||filing.filing_price", self.html)
        self.assertIn("filing.offering_price", self.html)
        self.assertIn("filing.current_price", self.html)
        self.assertIn("Delayed quote", self.html)

    def test_highlights_exact_stanford_bio_matches(self):
        self.assertIn("--cardinal:#8c1515", self.html)
        self.assertIn("person.stanford_university_bio===true", self.html)
        self.assertIn("Stanford University referenced in public bio", self.html)

    def test_has_no_fabricated_fallback_or_dead_navigation(self):
        self.assertNotIn("demoFilings", self.html)
        self.assertNotIn("Companies</button>", self.html)
        self.assertNotIn("Settings</button>", self.html)
        self.assertIn("No qualifying domestic IPO filings", self.html)

    def test_does_not_insert_feed_values_with_inner_html(self):
        self.assertNotIn(".innerHTML", self.html)

    def test_sample_feed_matches_public_schema(self):
        self.assertEqual(self.feed["schema_version"], 1)
        self.assertIsInstance(self.feed["filings"], list)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs" / "index.html"


class DashboardFreshnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")

    def test_edgar_refresh_timestamp_is_shown_near_header(self):
        self.assertIn('id="edgarRefresh"', self.html)
        self.assertIn("EDGAR data last refreshed:", self.html)
        header_index = self.html.index('<header class="top">')
        freshness_index = self.html.index('id="edgarRefresh"')
        activity_index = self.html.index('<section class="activity">')
        self.assertLess(header_index, freshness_index)
        self.assertLess(freshness_index, activity_index)

    def test_edgar_refresh_uses_feed_generated_at_in_pacific_time(self):
        self.assertIn("function edgarRefreshLabel(value)", self.html)
        self.assertIn('timeZone:"America/Los_Angeles"', self.html)
        self.assertIn('`${formatted} PT`', self.html)
        self.assertIn("payload.generated_at", self.html)
        self.assertIn('$("edgarRefresh").textContent=`EDGAR data last refreshed: ${edgarRefreshLabel(payload.generated_at)}`', self.html)
        self.assertIn('$("edgarRefresh").textContent="EDGAR data last refreshed: unavailable"', self.html)


if __name__ == "__main__":
    unittest.main()

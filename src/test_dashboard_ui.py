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
            "queueView", "savedView", "search", "formFilter",
            "statusFilter", "dateFilter", "sortBy", "clearFilters", "resultCount",
            "detailFilingPrice", "detailIpoPrice", "detailCurrentPrice",
            "detailPriceUpdated", "startReview", "markReview", "toggleSaved",
            "openSec", "reload", "resetColumns",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertNotIn('id="priorityFilter"', self.html)

    def test_queue_supports_researcher_filtering_and_sorting(self):
        self.assertIn("function populateFormFilter()", self.html)
        self.assertIn("function dateWithin(filed,days)", self.html)
        self.assertIn('sort==="value-desc"', self.html)
        self.assertIn('sort==="owners-desc"', self.html)
        self.assertIn("function clearFilters()", self.html)
        self.assertIn("Last 30 days", self.html)

    def test_filed_date_uses_friendly_format(self):
        self.assertIn('month:"short",day:"numeric",year:"numeric"', self.html)
        self.assertIn('dateLabel(filing.filed)', self.html)
        self.assertIn('/^\\d{8}$/.test(raw)', self.html)

    def test_main_table_uses_requested_default_column_order(self):
        expected_labels = (
            "Company Name", "Ticker", "Form", "Stage", "Filed",
            "IPO Size / Offering Value", "Filing Price", "Final IPO Price",
            "Current Price", "Public Signals",
        )
        positions = [self.html.index(f'>{label}</th>') for label in expected_labels]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Public Signals</th>", self.html)
        self.assertNotIn("<th>Priority</th>", self.html)
        self.assertNotIn("<th>Status</th>", self.html)
        self.assertIn("money(filing.ipo_size||filing.value)", self.html)
        self.assertIn('filing.ticker||"—"', self.html)

    def test_columns_are_drag_reorderable_and_persistent(self):
        for index in range(10):
            self.assertIn(f'draggable="true" data-col="{index}"', self.html)
        self.assertIn('research-monitor:column-order', self.html)
        self.assertIn("function setupColumnDrag()", self.html)
        self.assertIn("function applyColumnOrder()", self.html)
        self.assertIn("function saveColumnOrder(order)", self.html)
        self.assertIn('storageRemove("research-monitor:column-order")', self.html)
        self.assertIn('id="resetColumns"', self.html)

    def test_displays_all_requested_price_fields(self):
        self.assertIn("Filing Price</th>", self.html)
        self.assertIn("Final IPO Price</th>", self.html)
        self.assertIn("Current Price</th>", self.html)
        self.assertIn("filing.price_range||filing.filing_price", self.html)
        self.assertIn("filing.offering_price", self.html)
        self.assertIn("filing.current_price", self.html)
        self.assertIn("Delayed quote", self.html)

    def test_highlights_only_confirmed_stanford_beneficial_owners(self):
        self.assertIn("--cardinal:#8c1515", self.html)
        self.assertIn(".stanford-company{color:var(--cardinal);font-weight:800}", self.html)
        self.assertIn(".stanford-person{color:var(--cardinal);font-weight:800}", self.html)
        self.assertIn(
            "function isStanfordBeneficialOwner(person){const shares=Number(person.shares);return person.stanford_university_bio===true&&Number.isFinite(shares)&&shares>0}",
            self.html,
        )
        self.assertIn(
            "function hasStanfordBeneficialOwner(filing){return filing.people.some(isStanfordBeneficialOwner)}",
            self.html,
        )
        self.assertIn(
            'hasStanfordBeneficialOwner(filing)?"company stanford-company":"company"',
            self.html,
        )
        self.assertIn(
            'const matched=isStanfordBeneficialOwner(person);const node=text(matched?"strong":"span",matched?"stanford-person":""',
            self.html,
        )
        self.assertIn("stanford-s", self.html)
        self.assertIn("Confirmed Stanford-affiliated beneficial owner", self.html)
        self.assertIn("Named people & beneficial owners", self.html)

    def test_public_signals_are_searchable_and_rendered(self):
        self.assertIn('signals:Array.isArray(filing.signals)?filing.signals.map(String):[]', self.html)
        self.assertIn('...f.signals', self.html)
        self.assertIn('filing.signals.length', self.html)
        self.assertIn('filing.signals[0]', self.html)

    def test_monthly_activity_replaces_summary_counters(self):
        self.assertIn('id="monthCount"', self.html)
        self.assertIn('id="monthlyChart"', self.html)
        self.assertIn("function renderMonthlyActivity()", self.html)
        self.assertIn('String(filing.form).toUpperCase()!=="424B4"', self.html)
        self.assertIn('start=new Date(Date.UTC(2026,5,1))', self.html)
        self.assertNotIn('for(let i=11;i>=0;i--)', self.html)
        self.assertIn('.bar.current{background:var(--cardinal);animation:pulse', self.html)
        self.assertIn('@media(prefers-reduced-motion:reduce)', self.html)
        self.assertNotIn('id="newCount"', self.html)
        self.assertNotIn('id="peopleCount"', self.html)
        self.assertNotIn('id="offeringTotal"', self.html)

    def test_has_no_fabricated_fallback_or_dead_navigation(self):
        self.assertNotIn("demoFilings", self.html)
        self.assertNotIn("Companies</button>", self.html)
        self.assertNotIn("Settings</button>", self.html)
        self.assertIn("No qualifying domestic IPO filings", self.html)

    def test_does_not_insert_feed_values_with_inner_html(self):
        self.assertNotIn(".innerHTML", self.html)

    def test_prospect_liquidity_ui_and_front_page_flags(self):
        for value in ("personDetail", "personCurrentValue", "personIpoValue", "personCashRealized", "personLiquidValue", "personLockedValue", "personLockupEnd"):
            self.assertIn(f'id="{value}"', self.html)
        self.assertIn("function ipoSizeBucket(value)", self.html)
        self.assertIn('"$500M+"', self.html)
        self.assertIn("stanford-s", self.html)
        self.assertIn("showPerson(person,filing)", self.html)

    def test_published_feed_retains_confirmed_stanford_beneficial_owner(self):
        matches = [
            person
            for filing in self.feed.get("filings", [])
            for person in filing.get("people", [])
            if person.get("stanford_university_bio") is True
            and isinstance(person.get("shares"), (int, float))
            and person.get("shares", 0) > 0
        ]
        self.assertTrue(
            matches,
            "Historical feed must retain at least one confirmed Stanford beneficial-owner holding.",
        )

    def test_sample_feed_matches_public_schema(self):
        self.assertEqual(self.feed["schema_version"], 1)
        self.assertIsInstance(self.feed["filings"], list)


if __name__ == "__main__":
    unittest.main()

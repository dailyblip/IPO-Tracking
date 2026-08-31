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
            "statusFilter", "dateFilter", "sizeFilter", "sortBy", "clearFilters", "resultCount",
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

    def test_ipo_size_filter_defaults_to_any_size_and_keeps_thresholds(self):
        self.assertIn('<option value="">Any size</option>', self.html)
        expected_options = (
            ('100000000', '$100M+'),
            ('250000000', '$250M+'),
            ('500000000', '$500M+'),
            ('1000000000', '$1B+'),
            ('5000000000', '$5B+'),
        )
        for value, label in expected_options:
            self.assertIn(f'<option value="{value}">{label}</option>', self.html)
        self.assertIn('sizeValue=$("sizeFilter").value,minSize=sizeValue?Number(sizeValue):null', self.html)
        self.assertIn('rawOfferingValue=f.ipo_size??f.value', self.html)
        self.assertIn('minSize===null||(hasOfferingValue&&offeringValue>=minSize)', self.html)
        self.assertIn('$("sizeFilter").value=""', self.html)
        self.assertIn('["formFilter","statusFilter","dateFilter","sizeFilter","sortBy"]', self.html)

    def test_filed_date_uses_friendly_format(self):
        self.assertIn('month:"short",day:"numeric",year:"numeric"', self.html)
        self.assertIn('dateLabel(filingDateValue(filing))', self.html)
        self.assertIn('dateLabel(pricingDateValue(filing))', self.html)
        self.assertIn('/^\\d{8}$/.test(raw)', self.html)

    def test_main_table_uses_locked_column_order(self):
        expected_labels = (
            "Company Name", "Ticker", "Form", "Stage", "Filed", "Pricing Date",
            "IPO Size / Offering Value", "Filing Price", "Final IPO Price",
            "Current Price", "Public Signals",
        )
        positions = [self.html.index(f'>{label}</th>') for label in expected_labels]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn(">Priced</th>", self.html)
        self.assertNotIn("<th>Priority</th>", self.html)
        self.assertNotIn("<th>Status</th>", self.html)
        self.assertIn("money(filing.ipo_size||filing.value)", self.html)
        self.assertIn('filing.ticker||"—"', self.html)
        self.assertIn('data-col="5">Pricing Date</th>', self.html)
        self.assertIn('data-col="10">Public Signals</th>', self.html)

    def test_public_signals_surface_in_main_queue_without_html_injection(self):
        self.assertIn('filing.signals.length?filing.signals.join(" · "):"—"', self.html)
        self.assertIn('data-col="10">Public Signals</th>', self.html)
        self.assertNotIn(".innerHTML", self.html)

    def test_columns_are_drag_reorderable_and_persistent(self):
        for index in range(11):
            self.assertIn(f'draggable="true" data-col="{index}"', self.html)
        self.assertNotIn('draggable="true" data-col="11"', self.html)
        self.assertIn('research-monitor:column-order', self.html)
        self.assertIn("function setupColumnDrag()", self.html)
        self.assertIn("function applyColumnOrder()", self.html)
        self.assertIn("function saveColumnOrder(order)", self.html)
        self.assertIn('storageRemove("research-monitor:column-order")', self.html)
        self.assertIn('id="resetColumns"', self.html)

    def test_main_table_keeps_data_fields_single_line_except_public_signals(self):
        self.assertIn('.table-wrap{overflow:auto}', self.html)
        self.assertIn('table{min-width:1735px}', self.html)
        self.assertIn('th[data-col]:not([data-col="10"]){white-space:nowrap}', self.html)
        self.assertIn('td[data-col]:not([data-col="0"]):not([data-col="10"]){white-space:nowrap}', self.html)
        self.assertIn('th[data-col="3"],td[data-col="3"]{min-width:125px}', self.html)
        self.assertIn('th[data-col="4"],td[data-col="4"]{min-width:140px}', self.html)
        self.assertIn('th[data-col="5"],td[data-col="5"]{min-width:140px}', self.html)
        self.assertIn('th[data-col="10"],td[data-col="10"]{min-width:270px;white-space:normal}', self.html)

    def test_displays_all_requested_price_fields(self):
        self.assertIn("Filing Price</th>", self.html)
        self.assertIn("Final IPO Price</th>", self.html)
        self.assertIn("Current Price</th>", self.html)
        self.assertIn("filing.filing_price||filing.price_range", self.html)
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
        self.assertNotIn('class="stanford-s"', self.html)
        self.assertNotIn("stanfordBadge", self.html)
        self.assertIn("Confirmed Stanford-affiliated beneficial owner", self.html)
        self.assertIn("Named people & beneficial owners", self.html)

    def test_monthly_activity_tracks_filings_and_pricings(self):
        self.assertIn('id="filingCount"', self.html)
        self.assertIn('id="pricingCount"', self.html)
        self.assertIn('id="monthlyChart"', self.html)
        self.assertIn("function renderMonthlyActivity()", self.html)
        self.assertIn("filingDateValue(filing)", self.html)
        self.assertIn("pricingDateValue(filing)", self.html)
        self.assertIn('start=new Date(Date.UTC(2026,5,1))', self.html)
        self.assertNotIn('for(let i=11;i>=0;i--)', self.html)
        self.assertIn('.bar.filing{background:#9ba8a0}', self.html)
        self.assertIn('.bar.pricing{background:var(--green)}', self.html)
        self.assertIn('.legend-dot.filing,.bar.filing{background:#9ba8a0}', self.html)
        self.assertIn('.legend-dot.pricing,.bar.pricing{background:var(--cardinal)}', self.html)
        self.assertIn('.bar.current{animation:pulse', self.html)
        self.assertIn('@media(prefers-reduced-motion:reduce)', self.html)

    def test_monthly_activity_advances_through_current_month(self):
        self.assertIn(
            'current=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),1))',
            self.html,
        )
        self.assertIn(
            'for(let d=new Date(start);d<=current;d=new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+1,1)))',
            self.html,
        )
        self.assertIn('index===months.length-1?" current":""', self.html)
        self.assertIn('const active=months[months.length-1]', self.html)

    def test_recent_activity_surfaces_lifecycle_events(self):
        self.assertIn('id="recentActivityList"', self.html)
        self.assertIn("Recent Activity", self.html)
        self.assertIn("function renderRecentActivity()", self.html)
        self.assertIn('kind:"Filed"', self.html)
        self.assertIn('kind:"Priced"', self.html)
        self.assertNotIn(">Priced</th>", self.html)
        self.assertIn('Newest activity', self.html)

    def test_recent_activity_ticker_cannot_be_stranded_paused_by_focus(self):
        self.assertIn('animation:recentTicker 34s linear infinite', self.html)
        self.assertIn('animation-play-state:running', self.html)
        self.assertNotIn('.recent-list:hover .recent-track', self.html)
        self.assertNotIn('.recent-list:focus-within .recent-track', self.html)
        self.assertIn('@media(prefers-reduced-motion:reduce)', self.html)
        self.assertIn('.recent-track{animation:none}', self.html)

    def test_has_no_fabricated_fallback_or_dead_navigation(self):
        self.assertNotIn("demoFilings", self.html)
        self.assertNotIn("Companies</button>", self.html)
        self.assertNotIn("Settings</button>", self.html)
        self.assertIn("No qualifying domestic IPO filings", self.html)

    def test_does_not_insert_feed_values_with_inner_html(self):
        self.assertNotIn(".innerHTML", self.html)

    def test_person_details_use_single_open_accordion_without_nested_modal(self):
        self.assertNotIn('id="personDetail"', self.html)
        self.assertNotIn('id="closePerson"', self.html)
        self.assertIn('className="owner-toggle"', self.html)
        self.assertIn('className="owner-panel"', self.html)
        self.assertIn('button.setAttribute("aria-expanded","false")', self.html)
        self.assertIn("function closeExpandedOwner()", self.html)
        self.assertIn("function buildPersonAccordion(person,filing)", self.html)
        self.assertIn('expandedOwner={button,panel}', self.html)
        self.assertIn('person.lockup_end_date', self.html)
        self.assertIn('person.liquidity_status', self.html)
        self.assertNotIn("Not applicable / unknown", self.html)
        self.assertNotIn("Liquidity classification not yet available for this holding", self.html)
        self.assertIn("No additional filing-supported liquidity details are available for this person.", self.html)
        self.assertNotIn("function ipoSizeBucket(value)", self.html)
        self.assertNotIn("size-pill", self.html)
        self.assertNotIn('class="stanford-s"', self.html)
        self.assertNotIn("stanfordBadge", self.html)

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

    def test_published_feed_populated_ipo_sizes_have_release_grade_provenance(self):
        for filing in self.feed.get("filings", []):
            with self.subTest(company=filing.get("company")):
                self.assertIn(filing.get("form"), {"S-1", "S-1/A", "424B4"})
                value = filing.get("value")
                if value in (None, "", "—"):
                    continue
                self.assertIsInstance(value, (int, float))
                self.assertGreater(value, 0)
                self.assertEqual(filing.get("offering_size_confidence"), "High")
                self.assertTrue(str(filing.get("offering_size_source") or "").strip())

    def test_sample_feed_matches_public_schema(self):
        self.assertEqual(self.feed["schema_version"], 1)
        self.assertIsInstance(self.feed["filings"], list)


if __name__ == "__main__":
    unittest.main()
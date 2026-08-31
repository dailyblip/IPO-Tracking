from pathlib import Path
import unittest

from dashboard_export import _csv_rows


DASHBOARD = Path(__file__).resolve().parents[1] / "docs" / "index.html"


class DashboardAuthoritativePricingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = DASHBOARD.read_text(encoding="utf-8")

    def test_pricing_date_never_falls_back_to_424b4_filing_date(self):
        self.assertIn(
            'function pricingDateValue(filing){return filing.pricing_date||""}',
            self.html,
        )
        self.assertNotIn(
            'function pricingDateValue(filing){return filing.pricing_date||(String(filing.form).toUpperCase()==="424B4"?filing.filed:"")||""}',
            self.html,
        )

    def test_canonical_filing_price_wins_over_legacy_range(self):
        canonical = 'filingPrice(filing.filing_price||filing.price_range)'
        legacy = 'filingPrice(filing.price_range||filing.filing_price)'
        self.assertGreaterEqual(self.html.count(canonical), 2)
        self.assertNotIn(legacy, self.html)

    def test_csv_export_prefers_canonical_filing_price(self):
        filing = {
            "company": "Example Corp",
            "filing_price": "$18.00–$20.00",
            "price_range": "$12.00–$14.00",
            "people": [],
        }
        row = next(_csv_rows([filing]))
        self.assertEqual(row["filing_price"], "$18.00–$20.00")


if __name__ == "__main__":
    unittest.main()

import unittest

from bs4 import BeautifulSoup

from lifecycle_reconciler import _apply_final_terms


class LifecyclePublicSchemaGuardTests(unittest.TestCase):
    def test_internal_size_conflict_marker_is_not_published(self):
        record = {
            "id": "0001193125-26-356916",
            "company": "Lyntris Inc.",
            "ticker": "LYNX",
            "cik": "0002132582",
            "accession_no": "0001193125-26-356916",
            "form": "424B4",
            "filed": "2026-08-19",
            "filing_date": "2026-07-01",
            "stage": "Priced",
            "pricing_date": "2026-08-19",
            "offering_price": 17.5,
            "offering_size_conflict": True,
            "people": [],
            "people_count": 0,
            "signals": [],
        }
        filing_meta = {
            "ticker": "LYNX",
            "cik": "0002132582",
            "accession_no": "0001193125-26-356916",
            "filing_date": "2026-08-19",
        }
        soup = BeautifulSoup(
            "<html><body>symbol: LYNX. The initial public offering price is "
            "$17.50 per share. THE OFFERING Common stock offered by us "
            "5,714,286 shares. Common stock offered by the selling stockholders "
            "11,285,714 shares.</body></html>",
            "html.parser",
        )

        result = _apply_final_terms(record, filing_meta, soup)

        self.assertIsNotNone(result)
        self.assertEqual(result["value"], 297_500_000.0)
        self.assertEqual(result["offering_size_confidence"], "High")
        self.assertNotIn("offering_size_conflict", result)


if __name__ == "__main__":
    unittest.main()

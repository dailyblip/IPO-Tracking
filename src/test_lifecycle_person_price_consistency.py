import unittest

from bs4 import BeautifulSoup

from lifecycle_reconciler import _repair_final_record


class LifecyclePersonPriceConsistencyTests(unittest.TestCase):
    def test_final_price_repair_recomputes_only_supported_person_ipo_values(self):
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
            "pricing_date": "2026-08-18",
            "offering_price": 20.0,
            "value": None,
            "value_label": None,
            "current_price": 22.0,
            "price_updated": "2026-09-04T20:00:00+00:00",
            "people": [
                {
                    "name": "Supported Holder",
                    "shares": 100,
                    "shares_sold_ipo": 25,
                    "ipo_value": 2000.0,
                    "cash_realized_ipo": 500.0,
                    "cash_value": 2200.0,
                },
                {
                    "name": "No Sale Quantity",
                    "shares": 50,
                    "ipo_value": 1000.0,
                    "cash_realized_ipo": 125.0,
                },
            ],
            "people_count": 2,
            "signals": ["Offering priced at $20.00 per share"],
        }
        meta = {
            "company_name": "Lyntris Inc.",
            "ticker": "LYNX",
            "cik": "0002132582",
            "accession_no": "0001193125-26-356916",
            "form_type": "424B4",
            "filing_date": "2026-08-19",
        }
        soup = BeautifulSoup(
            "<html><body>symbol: LYNX. The initial public offering price is "
            "$17.50 per share. THE OFFERING Common stock offered by us "
            "5,714,286 shares. Common stock offered by the selling stockholders "
            "11,285,714 shares.</body></html>",
            "html.parser",
        )

        repaired = _repair_final_record(record, meta, soup)

        self.assertIsNotNone(repaired)
        self.assertEqual(repaired["offering_price"], 17.5)
        supported = repaired["people"][0]
        self.assertEqual(supported["ipo_value"], 1750.0)
        self.assertEqual(supported["cash_realized_ipo"], 437.5)
        self.assertEqual(supported["cash_value"], 2200.0)

        unsupported_sale = repaired["people"][1]
        self.assertEqual(unsupported_sale["ipo_value"], 875.0)
        self.assertNotIn("cash_realized_ipo", unsupported_sale)


if __name__ == "__main__":
    unittest.main()

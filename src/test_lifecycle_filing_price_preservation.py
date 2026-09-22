import unittest

from bs4 import BeautifulSoup

from lifecycle_reconciler import _promote_prepricing_record


class LifecycleFilingPricePreservationTests(unittest.TestCase):
    def test_s1_to_424b4_promotion_preserves_authoritative_preliminary_price_provenance(self):
        preliminary_source = {
            "source": "SEC EDGAR",
            "form": "S-1/A",
            "filing_date": "2026-08-12",
            "accession_no": "0001193125-26-346328",
            "file_number": "333-300001",
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/2132582/"
                "000119312526346328/0001193125-26-346328-index.htm"
            ),
        }
        prepricing = {
            "id": "0001193125-26-346328",
            "company": "Lyntris Inc.",
            "ticker": "LYNX",
            "cik": "0002132582",
            "accession_no": "0001193125-26-346328",
            "form": "S-1/A",
            "filed": "2026-08-12",
            "filing_date": "2026-07-01",
            "stage": "Pre-pricing",
            "priority": "High",
            "status": "New",
            "value": None,
            "value_label": None,
            "price_range": "19-22",
            "filing_price": "19-22",
            "filing_price_source": preliminary_source,
            "people": [],
            "people_count": 0,
            "signals": ["Registration statement amended — IPO remains pre-pricing"],
            "sec_url": preliminary_source["sec_url"],
        }
        final_meta = {
            "company_name": "Lyntris Inc.",
            "ticker": "LYNX",
            "cik": "0002132582",
            "accession_no": "0001193125-26-356916",
            "form_type": "424B4",
            "filing_date": "2026-08-19",
        }
        final_soup = BeautifulSoup(
            "<html><body>"
            "symbol: LYNX. The initial public offering price is $17.50 per share. "
            "THE OFFERING Common stock offered by us 5,714,286 shares. "
            "Common stock offered by the selling stockholders 11,285,714 shares."
            "</body></html>",
            "html.parser",
        )

        promoted = _promote_prepricing_record(prepricing, final_meta, final_soup)

        self.assertIsNotNone(promoted)
        self.assertEqual(promoted["form"], "424B4")
        self.assertEqual(promoted["stage"], "Priced")
        self.assertEqual(promoted["offering_price"], 17.5)
        self.assertEqual(promoted["filing_price"], "19-22")
        self.assertEqual(promoted["price_range"], "19-22")
        self.assertEqual(promoted["filing_price_source"], preliminary_source)
        self.assertEqual(
            promoted["filing_price_source"]["accession_no"],
            "0001193125-26-346328",
        )
        self.assertIn("0001193125-26-356916", promoted["sec_url"])
        self.assertNotEqual(
            promoted["sec_url"],
            promoted["filing_price_source"]["sec_url"],
        )

    def test_same_ticker_promotion_drops_prepricing_quote_without_losing_filing_price_provenance(self):
        preliminary_source = {
            "source": "SEC EDGAR",
            "form": "S-1/A",
            "filing_date": "2026-08-12",
            "accession_no": "0001193125-26-346328",
            "file_number": "333-300001",
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/2132582/"
                "000119312526346328/0001193125-26-346328-index.htm"
            ),
        }
        prepricing = {
            "id": "0001193125-26-346328",
            "company": "Lyntris Inc.",
            "ticker": "LYNX",
            "cik": "0002132582",
            "accession_no": "0001193125-26-346328",
            "form": "S-1/A",
            "filed": "2026-08-12",
            "filing_date": "2026-07-01",
            "stage": "Pre-pricing",
            "priority": "High",
            "status": "New",
            "price_range": "19-22",
            "filing_price": "19-22",
            "filing_price_source": preliminary_source,
            "current_price": 99.0,
            "price_updated": "2026-08-12T15:00:00+00:00",
            "value": None,
            "value_label": None,
            "people": [],
            "people_count": 0,
            "signals": [
                "Registration statement amended — IPO remains pre-pricing",
                "Current market value is approximately $99.00 per share",
            ],
            "sec_url": preliminary_source["sec_url"],
        }
        final_meta = {
            "company_name": "Lyntris Inc.",
            "ticker": "LYNX",
            "cik": "0002132582",
            "accession_no": "0001193125-26-356916",
            "form_type": "424B4",
            "filing_date": "2026-08-19",
        }
        final_soup = BeautifulSoup(
            "<html><body>"
            "symbol: LYNX. The initial public offering price is $17.50 per share. "
            "THE OFFERING Common stock offered by us 5,714,286 shares. "
            "Common stock offered by the selling stockholders 11,285,714 shares."
            "</body></html>",
            "html.parser",
        )

        promoted = _promote_prepricing_record(prepricing, final_meta, final_soup)

        self.assertIsNotNone(promoted)
        self.assertEqual(promoted["ticker"], "LYNX")
        self.assertNotIn("current_price", promoted)
        self.assertNotIn("price_updated", promoted)
        self.assertNotIn("current market value", " ".join(promoted["signals"]).casefold())
        self.assertEqual(promoted["filing_price"], "19-22")
        self.assertEqual(promoted["price_range"], "19-22")
        self.assertEqual(promoted["filing_price_source"], preliminary_source)


if __name__ == "__main__":
    unittest.main()

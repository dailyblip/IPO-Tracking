import unittest

from bs4 import BeautifulSoup

from lifecycle_reconciler import _promote_prepricing_record


class LifecycleFixedFilingPriceHandoffTests(unittest.TestCase):
    def test_promotion_preserves_authoritative_fixed_preliminary_price_and_source(self):
        source = {
            "source": "SEC S-1/A",
            "form": "S-1/A",
            "filing_date": "2026-08-12",
            "accession_no": "0001193125-26-346328",
            "sec_url": "https://www.sec.gov/Archives/edgar/data/2132582/000119312526346328/0001193125-26-346328-index.html",
        }
        prepricing = {
            "id": "s1:0002132582",
            "company": "Example Operating Co.",
            "ticker": "EXMP",
            "cik": "0002132582",
            "accession_no": "0001193125-26-346328",
            "form": "S-1/A",
            "filed": "2026-08-12",
            "filing_date": "2026-07-01",
            "stage": "Pre-pricing",
            "filing_price": 17.5,
            "price_range": None,
            "filing_price_source": source,
            "signals": ["Registration statement amended — IPO remains pre-pricing"],
        }
        final_meta = {
            "company_name": "Example Operating Co.",
            "ticker": "EXMP",
            "cik": "0002132582",
            "accession_no": "0001193125-26-356916",
            "form_type": "424B4",
            "filing_date": "2026-08-19",
        }
        final_soup = BeautifulSoup(
            "<html><body>symbol: EXMP. The initial public offering price is $18.00 per share. "
            "THE OFFERING Common stock offered by us 5,000,000 shares.</body></html>",
            "html.parser",
        )

        promoted = _promote_prepricing_record(prepricing, final_meta, final_soup)

        self.assertIsNotNone(promoted)
        self.assertEqual(promoted["form"], "424B4")
        self.assertEqual(promoted["stage"], "Priced")
        self.assertEqual(promoted["offering_price"], 18.0)
        self.assertEqual(promoted["filing_price"], 17.5)
        self.assertIsNone(promoted["price_range"])
        self.assertEqual(promoted["filing_price_source"], source)


if __name__ == "__main__":
    unittest.main()

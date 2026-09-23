import unittest

from bs4 import BeautifulSoup

import filing_parser
import s1_monitor


class ClassQualifiedOfferingTermsTests(unittest.TestCase):
    def test_accelevation_style_class_a_rows_reconcile_base_ipo(self):
        soup = BeautifulSoup(
            """
            <html><body>
            30,000,000 Shares Class A Common Stock
            This is our initial public offering.
            THE OFFERING
            Class A common stock offered by us | 8,635,165 shares.
            Class A common stock offered by the selling stockholders | 21,364,835 shares.
            The underwriters have an option to purchase an additional 4,500,000 shares.
            We estimate the initial public offering price will be between $20.00 and $24.00 per share.
            </body></html>
            """,
            "lxml",
        )

        terms = filing_parser.extract_offering_terms(soup)

        self.assertEqual(terms["total_shares"], 30_000_000)
        self.assertEqual(terms["primary_shares"], 8_635_165)
        self.assertEqual(terms["secondary_shares"], 21_364_835)
        self.assertEqual(terms["confidence"], "High")
        self.assertFalse(terms["conflict"])
        self.assertIn("THE OFFERING primary + secondary rows", terms["source"])

        parsed = {
            "cover_page": {
                "offering_size_shares": terms["total_shares"],
                "offering_size_confidence": terms["confidence"],
                "offering_size_conflict": terms["conflict"],
            }
        }
        self.assertEqual(
            s1_monitor._extract_ipo_size(
                soup.get_text(" ", strip=True),
                parsed,
                {"range_low": 20.0, "range_high": 24.0},
            ),
            660_000_000,
        )

    def test_accelevation_rows_beyond_cover_window_reconcile_base_ipo(self):
        # Real S-1/A documents can place the authoritative THE OFFERING table
        # well beyond the first 50k of flattened text. Keep the cover narrative
        # realistic: the issuer is named in third person, while selling-holder
        # shares are also disclosed before the deep table.
        filler = " risk disclosure text" * 4000
        soup = BeautifulSoup(
            f"""
            <html><body>
            Accelevation Holdings Corp. is offering 8,635,165 shares of Class A common stock
            and the selling stockholders named in this prospectus are offering 21,364,835
            shares of Class A common stock to be sold in the offering.
            This is the initial public offering of our Class A common stock.
            We estimate the initial public offering price will be between $20.00 and $24.00 per share.
            {filler}
            THE OFFERING
            Class A common stock offered by us | 8,635,165 shares.
            Class A common stock offered by the selling stockholders | 21,364,835 shares.
            Underwriters' option to purchase additional shares | 4,500,000 shares.
            </body></html>
            """,
            "lxml",
        )

        flattened = soup.get_text(" ", strip=True)
        self.assertGreater(flattened.index("THE OFFERING"), 50_000)

        terms = filing_parser.extract_offering_terms(soup)

        self.assertEqual(terms["total_shares"], 30_000_000)
        self.assertEqual(terms["primary_shares"], 8_635_165)
        self.assertEqual(terms["secondary_shares"], 21_364_835)
        self.assertEqual(terms["confidence"], "High")
        self.assertFalse(terms["conflict"])
        self.assertIn("THE OFFERING primary + secondary rows", terms["source"])

        parsed = {
            "cover_page": {
                "offering_size_shares": terms["total_shares"],
                "offering_size_confidence": terms["confidence"],
                "offering_size_conflict": terms["conflict"],
            }
        }
        self.assertEqual(
            s1_monitor._extract_ipo_size(
                flattened,
                parsed,
                {"range_low": 20.0, "range_high": 24.0},
            ),
            660_000_000,
        )


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

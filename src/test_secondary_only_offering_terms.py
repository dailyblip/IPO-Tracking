import unittest

from bs4 import BeautifulSoup

import filing_parser


class SecondaryOnlyOfferingTermsTests(unittest.TestCase):
    def test_secondary_only_ipo_preserves_explicit_selling_holder_shares(self):
        soup = BeautifulSoup(
            """
            <html><body>
            PRELIMINARY PROSPECTUS
            35,000,000 Shares Class A Common Stock
            This is the initial public offering of our Class A common stock.
            The Selling Stockholders (as defined below) are offering 35,000,000
            shares of our Class A common stock. We will not receive any proceeds
            from the sale of shares by the Selling Stockholders in this offering.
            The initial public offering price is expected to be between $18.00
            and $20.00 per share.
            </body></html>
            """,
            "lxml",
        )

        terms = filing_parser.extract_offering_terms(soup)

        self.assertEqual(terms["total_shares"], 35_000_000)
        self.assertIsNone(terms["primary_shares"])
        self.assertEqual(terms["secondary_shares"], 35_000_000)
        self.assertEqual(terms["confidence"], "High")
        self.assertFalse(terms["conflict"])
        self.assertIn("explicit selling-holder cover statement", terms["source"])

    def test_non_ipo_resale_statement_does_not_become_ipo_secondary_terms(self):
        soup = BeautifulSoup(
            """
            <html><body>
            This prospectus relates to the resale of previously issued shares.
            The Selling Stockholders are offering 35,000,000 shares of common stock.
            We will not receive any proceeds from the sale of shares by the Selling
            Stockholders.
            </body></html>
            """,
            "lxml",
        )

        terms = filing_parser.extract_offering_terms(soup)

        self.assertIsNone(terms["total_shares"])
        self.assertIsNone(terms["primary_shares"])
        self.assertIsNone(terms["secondary_shares"])


if __name__ == "__main__":
    unittest.main()

import unittest

from bs4 import BeautifulSoup

import filing_parser


def _soup(text):
    return BeautifulSoup(f"<html><body>{text}</body></html>", "html.parser")


class FinalOfferingShareReconciliationTests(unittest.TestCase):
    def test_jersey_mikes_selling_verb_and_secondary_leg(self):
        terms = filing_parser.extract_offering_terms(_soup("""
        43,478,261 Shares Jersey Mike's Subs Inc. Class A Common Stock.
        This is the initial public offering of shares of Class A common stock of Jersey Mike's Subs Inc.
        We are selling 13,782,609 shares of our Class A common stock and the selling stockholders
        identified in this prospectus are offering 29,695,652 shares of Class A common stock.
        The initial public offering price is $23.00 per share.
        The underwriters have an option to purchase up to an additional 6,521,739 shares.
        """))
        self.assertEqual(terms["total_shares"], 43_478_261)
        self.assertEqual(terms["primary_shares"], 13_782_609)
        self.assertEqual(terms["secondary_shares"], 29_695_652)
        self.assertFalse(terms["conflict"])
        self.assertEqual(terms["total_shares"] * 23, 1_000_000_003)

    def test_reformation_aggregate_selling_holder_phrase(self):
        terms = filing_parser.extract_offering_terms(_soup("""
        PRELIMINARY PROSPECTUS 14,062,500 Shares Reformation Inc. Common Stock.
        This is the initial public offering of shares of common stock of Reformation Inc.
        We are offering 9,478,821 shares of our common stock, and the selling stockholders
        identified in this prospectus are offering an aggregate of 4,583,679 shares of our common stock.
        The public offering price is $15.00 per share.
        The selling stockholders granted the underwriters an option to purchase up to 2,109,375 additional shares.
        """))
        self.assertEqual(terms["total_shares"], 14_062_500)
        self.assertEqual(terms["primary_shares"], 9_478_821)
        self.assertEqual(terms["secondary_shares"], 4_583_679)
        self.assertFalse(terms["conflict"])
        self.assertEqual(terms["total_shares"] * 15, 210_937_500)

    def test_csquare_cover_title_preserves_base_total_and_primary_split(self):
        terms = filing_parser.extract_offering_terms(_soup("""
        PROSPECTUS 50,000,000 Shares Csquare, Inc. Common Stock.
        This is the initial public offering of shares of common stock of Csquare, Inc.
        We are offering 50,000,000 shares of common stock.
        The initial public offering price is $21.00 per share.
        The underwriters may purchase an additional 7,499,000 shares under their option.
        Later capitalization disclosure references 250,000,002 shares outstanding.
        """))
        self.assertEqual(terms["total_shares"], 50_000_000)
        self.assertEqual(terms["primary_shares"], 50_000_000)
        self.assertIsNone(terms["secondary_shares"])
        self.assertFalse(terms["conflict"])
        self.assertEqual(terms["total_shares"] * 21, 1_050_000_000)

    def test_aadx_an_initial_public_offering_title_beats_option_shares(self):
        terms = filing_parser.extract_offering_terms(_soup("""
        32,500,000 Shares Applied Aerospace & Defense, Inc. Common Stock.
        This is an initial public offering of Applied Aerospace & Defense, Inc.
        We are offering 32,500,000 shares of our common stock.
        The initial public offering price per share is $20.00.
        We have granted the underwriters an option to purchase up to an additional
        4,875,000 shares of common stock from us at the initial offering price.
        """))
        self.assertEqual(terms["total_shares"], 32_500_000)
        self.assertEqual(terms["primary_shares"], 32_500_000)
        self.assertIsNone(terms["secondary_shares"])
        self.assertFalse(terms["conflict"])
        self.assertEqual(terms["total_shares"] * 20, 650_000_000)

    def test_option_share_count_is_not_accepted_as_context_fallback_total(self):
        terms = filing_parser.extract_offering_terms(_soup("""
        This is an initial public offering of Example Corp.
        We have granted the underwriters an option to purchase up to an additional
        4,875,000 shares of common stock from us at the initial offering price.
        """))
        self.assertIsNone(terms["total_shares"])

    def test_cover_title_does_not_fold_overallotment_into_base_ipo(self):
        terms = filing_parser.extract_offering_terms(_soup("""
        PROSPECTUS 12,000,000 Shares Example Corp Common Stock.
        This is the initial public offering of shares of common stock of Example Corp.
        We are offering 12,000,000 shares of common stock.
        The underwriters have an option to purchase an additional 1,800,000 shares.
        """))
        self.assertEqual(terms["total_shares"], 12_000_000)
        self.assertEqual(terms["primary_shares"], 12_000_000)


if __name__ == "__main__":
    unittest.main()

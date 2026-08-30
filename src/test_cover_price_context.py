import os
import sys
import unittest

from bs4 import BeautifulSoup

os.environ.setdefault("SEC_EDGAR_USER_AGENT", "test test@example.com")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from filing_parser import extract_cover_page_data


def _soup(text: str) -> BeautifulSoup:
    return BeautifulSoup(f"<html><body>{text}</body></html>", "lxml")


class CoverOfferingPriceContextTests(unittest.TestCase):
    def test_blank_ipo_cover_does_not_promote_option_exercise_price(self):
        soup = _soup(
            "We currently expect that the initial public offering price will be "
            "between $      and $      per share of our common stock. "
            "Outstanding employee stock options had a weighted-average exercise "
            "price of $3.27 per share."
        )
        self.assertIsNone(extract_cover_page_data(soup)["offering_price"])

    def test_blank_ipo_cover_does_not_promote_unrelated_per_share_value(self):
        soup = _soup(
            "The initial public offering price per share is $      . "
            "For accounting purposes, another security was valued at $8.03 per share."
        )
        self.assertIsNone(extract_cover_page_data(soup)["offering_price"])

    def test_dilution_footnote_increment_is_not_fixed_ipo_price(self):
        soup = _soup(
            "<table><tr><td>Initial public offering price per share</td>"
            "<td>$</td><td>&emsp;</td></tr>"
            "<tr><td>(1) If the initial public offering price were to increase or "
            "decrease by $1.00 per share, then dilution would change accordingly."
            "</td></tr></table>"
        )
        self.assertIsNone(extract_cover_page_data(soup)["offering_price"])

    def test_explicit_initial_public_offering_price_still_parses(self):
        soup = _soup("The initial public offering price of $17.50 per share.")
        self.assertEqual(extract_cover_page_data(soup)["offering_price"], 17.50)

    def test_explicit_price_to_public_still_parses(self):
        soup = _soup("Price to public per share $24.00")
        self.assertEqual(extract_cover_page_data(soup)["offering_price"], 24.00)

    def test_explicit_table_ipo_price_still_parses(self):
        soup = _soup(
            "<table><tr><td>Initial public offering price per share</td>"
            "<td>$ 19.00</td></tr></table>"
        )
        self.assertEqual(extract_cover_page_data(soup)["offering_price"], 19.00)


if __name__ == "__main__":
    unittest.main()

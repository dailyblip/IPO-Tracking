import os
import sys
import unittest

from bs4 import BeautifulSoup

os.environ.setdefault("SEC_EDGAR_USER_AGENT", "test test@example.com")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import filing_parser


class FinalIpoPriceTableFallbackTests(unittest.TestCase):
    def _soup(self, html):
        return BeautifulSoup(html, "lxml")

    def test_recovers_final_price_when_sec_table_splits_label_and_amount_cells(self):
        soup = self._soup(
            """
            <html><body>
              <p>This is an initial public offering of 14,000,000 shares.</p>
              <table>
                <tr><th></th><th>Per Share</th><th>Total</th></tr>
                <tr>
                  <td>Initial public offering price</td>
                  <td>$</td><td>20.00</td>
                  <td>$</td><td>280,000,000</td>
                </tr>
              </table>
            </body></html>
            """
        )
        self.assertEqual(
            filing_parser.extract_cover_page_data(soup)["offering_price"], 20.0
        )

    def test_rejects_assumed_price_rows_from_preliminary_dilution_tables(self):
        soup = self._soup(
            """
            <html><body>
              <table>
                <tr>
                  <td>Assumed initial public offering price</td>
                  <td>$</td><td>21.50</td>
                </tr>
              </table>
            </body></html>
            """
        )
        self.assertIsNone(
            filing_parser.extract_cover_page_data(soup)["offering_price"]
        )

    def test_does_not_promote_unrelated_per_share_amount(self):
        soup = self._soup(
            """
            <html><body>
              <p>This is an initial public offering.</p>
              <table>
                <tr><td>Option exercise price per share</td><td>$</td><td>20.00</td></tr>
              </table>
            </body></html>
            """
        )
        self.assertIsNone(
            filing_parser.extract_cover_page_data(soup)["offering_price"]
        )


if __name__ == "__main__":
    unittest.main()

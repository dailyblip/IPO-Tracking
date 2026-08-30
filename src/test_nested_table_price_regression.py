import unittest

from bs4 import BeautifulSoup

from filing_parser import _extract_explicit_ipo_price_from_tables, extract_cover_page_data


class NestedTablePriceRegressionTests(unittest.TestCase):
    def test_wrapper_row_does_not_steal_sensitivity_increment(self):
        soup = BeautifulSoup(
            """
            <html><body>
              <table>
                <tr>
                  <td>
                    <table>
                      <tr>
                        <td>Initial public offering price</td>
                        <td>$</td>
                        <td></td>
                      </tr>
                      <tr>
                        <td>
                          Each $1.00 increase (decrease) in the assumed initial
                          public offering price would change our proceeds.
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </body></html>
            """,
            "lxml",
        )

        self.assertIsNone(_extract_explicit_ipo_price_from_tables(soup))
        self.assertIsNone(extract_cover_page_data(soup)["offering_price"])

    def test_leaf_row_rejects_assumed_price_sensitivity_increment(self):
        soup = BeautifulSoup(
            """
            <html><body>
              <table>
                <tr>
                  <td>Initial public offering price per share</td>
                  <td>$</td>
                  <td></td>
                  <td>
                    Each $1.00 increase (decrease) in the assumed initial public
                    offering price would increase (decrease) our net proceeds.
                  </td>
                </tr>
              </table>
            </body></html>
            """,
            "lxml",
        )

        self.assertIsNone(_extract_explicit_ipo_price_from_tables(soup))
        self.assertIsNone(extract_cover_page_data(soup)["offering_price"])

    def test_sensitivity_row_is_skipped_before_real_fixed_price(self):
        soup = BeautifulSoup(
            """
            <html><body>
              <table>
                <tr>
                  <td>Initial public offering price per share</td>
                  <td>
                    Each $1.00 increase (decrease) in the assumed initial public
                    offering price would change our proceeds.
                  </td>
                </tr>
                <tr>
                  <td>Price to the public per share</td>
                  <td>$20.00</td>
                </tr>
              </table>
            </body></html>
            """,
            "lxml",
        )

        self.assertEqual(_extract_explicit_ipo_price_from_tables(soup), 20.0)
        self.assertEqual(extract_cover_page_data(soup)["offering_price"], 20.0)

    def test_prose_sensitivity_context_does_not_become_fixed_price(self):
        soup = BeautifulSoup(
            """
            <html><body>
              <p>
                Initial public offering price per share $1.00 increase in the
                assumed initial public offering price would change our proceeds.
              </p>
            </body></html>
            """,
            "lxml",
        )

        self.assertIsNone(extract_cover_page_data(soup)["offering_price"])


if __name__ == "__main__":
    unittest.main()

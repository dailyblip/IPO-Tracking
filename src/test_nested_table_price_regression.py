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


if __name__ == "__main__":
    unittest.main()

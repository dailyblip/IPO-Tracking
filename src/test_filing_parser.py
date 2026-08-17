"""
Regression tests for filing_parser.extract_principal_stockholders'
false-positive table exclusion.

Run with: python -m unittest tests.test_filing_parser -v
(from the repo root, with SEC_EDGAR_USER_AGENT set to any value -
extract_principal_stockholders doesn't hit the network, but the
module-level import chain expects the env var to be resolvable if
fetch_document is ever called.)
"""

import os
import sys
import unittest

os.environ.setdefault("SEC_EDGAR_USER_AGENT", "test test@example.com")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bs4 import BeautifulSoup

from filing_parser import (
    extract_cover_page_data,
    extract_offering_size,
    extract_principal_stockholders,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


class ExtractPrincipalStockholdersTests(unittest.TestCase):
    def test_excludes_financial_highlights_decoy_table(self):
        """A row-level name+number table (financial highlights) that
        precedes the real ownership grid must not be mistaken for it,
        even though rows like "Revenues 10,500,000 12.5%" superficially
        resemble a holder/shares/percent row."""
        html = """
        <html><body>
        <p><b>PRINCIPAL STOCKHOLDERS</b></p>
        <table>
          <tr><td>Selected Financial Data</td><td>2023</td><td>2024</td></tr>
          <tr><td>Revenues</td><td>10,500,000</td><td>12.5%</td></tr>
          <tr><td>Net loss</td><td>2,300,000</td><td>3.1%</td></tr>
        </table>
        <table>
          <tr><th>Name of Beneficial Owner</th><th>Shares Beneficially Owned</th><th>Percent of Class</th></tr>
          <tr><td>Jane Smith</td><td>1,200,000</td><td>8.2%</td></tr>
        </table>
        </body></html>
        """
        result = extract_principal_stockholders(_soup(html))
        self.assertEqual(result, [{"name": "Jane Smith", "shares": 1200000, "percent": 8.2}])

    def test_excludes_underwriters_allocation_table(self):
        """An underwriters' share-allocation table ("Number of Shares"
        column) sitting between a false heading match and the real
        table must not be reported as ownership data."""
        html = """
        <html><body>
        <p><b>Principal Stockholders</b> ................. 88</p>
        <table><tr><td>Underwriters</td><td>Number of Shares</td></tr>
                <tr><td>Acme Capital</td><td>500,000</td></tr></table>
        </body></html>
        """
        result = extract_principal_stockholders(_soup(html))
        self.assertEqual(result, [])

    def test_accepts_clean_ownership_table(self):
        html = """
        <html><body>
        <h2>Security Ownership of Certain Beneficial Owners</h2>
        <table>
          <tr><th>Name and Address of Beneficial Owner</th><th>Number of Shares</th><th>Percentage of Class</th></tr>
          <tr><td>Alice Chen</td><td>3,400,000</td><td>22.1%</td></tr>
        </table>
        </body></html>
        """
        result = extract_principal_stockholders(_soup(html))
        self.assertEqual(result, [{"name": "Alice Chen", "shares": 3400000, "percent": 22.1}])

    def test_no_heading_returns_empty(self):
        html = "<html><body><p>No relevant section here.</p></body></html>"
        result = extract_principal_stockholders(_soup(html))
        self.assertEqual(result, [])


    def test_extracts_price_and_size_from_long_spaced_cover(self):
        html = f"""
        <html><body>
        <p>{"x" * 6000}</p>
        <p>This is the initial public offering of shares of common stock.</p>
        <p>We are offering 21,250,000 shares of our common stock.</p>
        <p>The initial public offering price per share is $ 18.00.</p>
        </body></html>
        """
        soup = _soup(html)
        self.assertEqual(extract_cover_page_data(soup)["offering_price"], 18.0)
        self.assertEqual(extract_offering_size(soup), 21_250_000)


    def test_skips_contents_heading_and_finds_later_ownership_table(self):
        unrelated = "".join(
            f"<table><tr><td>Unrelated table {index}</td></tr></table>"
            for index in range(5)
        )
        html = f"""
        <html><body>
        <p><b>PRINCIPAL STOCKHOLDERS</b> ........ 207</p>
        {unrelated}
        <h2>PRINCIPAL STOCKHOLDERS</h2>
        <table>
          <tr><th></th><th>Before Offering</th><th>After Offering</th></tr>
          <tr><th>Name of Beneficial Owner</th><th>Number of Shares of Common Stock Beneficially Owned</th><th>Percentage of Shares Beneficially Owned</th></tr>
          <tr><td>AH Bio Fund IV, L.P.(1)</td><td>9,132,420</td><td>13.9%</td></tr>
          <tr><td>All executive officers and directors as a group (10 persons)(2)</td><td>12,043,263</td><td>18.4%</td></tr>
        </table>
        </body></html>
        """
        result = extract_principal_stockholders(_soup(html))
        self.assertEqual(result[0]["name"], "AH Bio Fund IV, L.P.(1)")
        self.assertEqual(result[0]["shares"], 9_132_420)
        self.assertEqual(len(result), 2)


    def test_accepts_principal_and_selling_stockholders_heading(self):
        html = """
        <html><body>
        <p>PRINCIPAL AND SELLING STOCKHOLDERS</p>
        <table>
          <tr><th></th><th>Shares Beneficially Owned Prior to this Offering</th><th>Shares to be Sold</th><th>Shares Beneficially Owned After this Offering</th></tr>
          <tr><th>Name of Beneficial Owner</th><th>Number</th><th>Number</th><th>Percentage</th></tr>
          <tr><td>Entities affiliated with Permira (1)</td><td>32,078,948</td><td>2,987,199</td><td>49.2%</td></tr>
          <tr><td>All directors and executive officers as a group (8 persons)</td><td>4,123,456</td><td>—</td><td>6.1%</td></tr>
        </table>
        </body></html>
        """
        result = extract_principal_stockholders(_soup(html))
        self.assertEqual(result[0]["name"], "Entities affiliated with Permira (1)")
        self.assertEqual(result[0]["shares"], 32_078_948)
        self.assertEqual(result[0]["percent"], 49.2)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()

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

from filing_parser import extract_principal_stockholders


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


if __name__ == "__main__":
    unittest.main()

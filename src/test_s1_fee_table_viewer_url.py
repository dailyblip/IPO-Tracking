import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from s1_preliminary_price_gate import _load_sec_fee_terms


INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/data/2151905/000215190526000001/"
    "0002151905-26-000001-index.htm"
)
RAW_EXHIBIT_URL = (
    "https://www.sec.gov/Archives/edgar/data/2151905/000215190526000001/EXFILINGFEES.htm"
)

INDEX_HTML = """
<table>
  <tr>
    <td>2</td><td>FEE TABLE</td>
    <td><a href="/ix?doc=%2FArchives%2Fedgar%2Fdata%2F2151905%2F000215190526000001%2FEXFILINGFEES.htm">EXFILINGFEES.htm</a></td>
    <td>EX-FILING FEES</td><td>23141</td>
  </tr>
</table>
"""

DIRECT_INDEX_HTML = """
<table>
  <tr>
    <td>2</td><td>FEE TABLE</td>
    <td><a href="/Archives/edgar/data/2151905/000215190526000001/EXFILINGFEES.htm">EXFILINGFEES.htm</a></td>
    <td>EX-FILING FEES</td><td>23141</td>
  </tr>
</table>
"""

FEE_HTML = """
<table>
  <tr>
    <td>Fees to be Paid</td><td></td><td>Equity</td><td>Ordinary</td>
    <td>457(a)</td><td>100,000</td><td>$ 5.00</td><td>$ 500,000.00</td>
    <td>0.0001381</td><td>$ 69.05</td>
  </tr>
</table>
"""


class FeeTableViewerUrlTests(unittest.TestCase):
    def _load_with_index(self, index_html):
        calls = []

        def fake_fetch(url):
            calls.append(url)
            if url == INDEX_URL:
                return BeautifulSoup(index_html, "lxml")
            if url == RAW_EXHIBIT_URL:
                return BeautifulSoup(FEE_HTML, "lxml")
            raise AssertionError(f"unexpected SEC fetch: {url}")

        with patch("s1_preliminary_price_gate.filing_parser.fetch_document", side_effect=fake_fetch):
            terms = _load_sec_fee_terms({"company": "La Beaute Inc.", "sec_url": INDEX_URL})
        return terms, calls

    def test_inline_xbrl_viewer_link_is_unwrapped_to_same_accession_exhibit(self):
        terms, calls = self._load_with_index(INDEX_HTML)
        self.assertEqual(
            terms,
            {"shares": 100_000, "price": 5.0, "aggregate": 500_000.0},
        )
        self.assertEqual(calls, [INDEX_URL, RAW_EXHIBIT_URL])

    def test_direct_archive_exhibit_link_remains_supported(self):
        terms, calls = self._load_with_index(DIRECT_INDEX_HTML)
        self.assertEqual(
            terms,
            {"shares": 100_000, "price": 5.0, "aggregate": 500_000.0},
        )
        self.assertEqual(calls, [INDEX_URL, RAW_EXHIBIT_URL])


if __name__ == "__main__":
    unittest.main()

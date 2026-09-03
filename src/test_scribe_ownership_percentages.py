import unittest

from bs4 import BeautifulSoup

from ownership_parser import parse_ownership_table


class ScribeOwnershipPercentageTests(unittest.TestCase):
    def test_rowspan_header_keeps_before_and_after_percentages_aligned(self):
        """Match the SEC layout used by Scribe Therapeutics' 2026 424B4.

        The owner/number headings span the percentage subheader row, while
        Before Offering and After Offering sit only beneath the percentage
        heading. Omitting those rowspans from the parser grid shifts the first
        percentage into the after field and drops the actual after percentage.
        """
        html = """<table>
        <tr>
          <th rowspan='2'>Named Beneficial Owner</th>
          <th rowspan='2' colspan='3'>Number of Shares Beneficially Owned</th>
          <th colspan='6'>Percentage of Shares Beneficially Owned</th>
        </tr>
        <tr>
          <th colspan='3'>Before Offering</th>
          <th colspan='3'>After Offering</th>
        </tr>
        <tr>
          <td>Benjamin L. Oakes, Ph.D. (1)</td>
          <td></td><td>660,998</td><td></td>
          <td></td><td>7.61</td><td>%</td>
          <td></td><td>3.72</td><td>%</td>
        </tr>
        </table>"""
        rows = parse_ownership_table(BeautifulSoup(html, "lxml").find("table"))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["name"], "Benjamin L. Oakes, Ph.D.")
        self.assertEqual(row["percent_before"], 7.61)
        self.assertEqual(row["percent_after"], 3.72)


if __name__ == "__main__":
    unittest.main()

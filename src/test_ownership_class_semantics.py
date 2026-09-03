import unittest

from bs4 import BeautifulSoup

from ownership_parser import parse_ownership_table


class OwnershipClassSemanticsTests(unittest.TestCase):
    def test_voting_power_and_class_percentages_do_not_become_generic_ownership(self):
        """Dual-class voting/class percentages are not generic beneficial ownership %."""
        html = """<table>
        <tr>
          <th>Name of beneficial owner</th>
          <th colspan='5'>Shares Beneficially Owned Before the Offering</th>
          <th colspan='5'>Shares Beneficially Owned After the Offering</th>
        </tr>
        <tr>
          <th></th>
          <th colspan='2'>Class A Common Stock</th>
          <th colspan='2'>Class B Common Stock</th>
          <th>% of Total Voting Power</th>
          <th colspan='2'>Class A Common Stock</th>
          <th colspan='2'>Class B Common Stock</th>
          <th>% of Total Voting Power</th>
        </tr>
        <tr>
          <th></th>
          <th>Shares</th><th>%</th>
          <th>Shares</th><th>%</th>
          <th></th>
          <th>Shares</th><th>%</th>
          <th>Shares</th><th>%</th>
          <th></th>
        </tr>
        <tr>
          <td>Thomas Hendrix (3)(9)</td>
          <td>—</td><td>—</td><td>11,578,308</td><td>100</td><td>62.5</td>
          <td>—</td><td>—</td><td>11,578,308</td><td>100</td><td>60.8</td>
        </tr>
        </table>"""
        rows = parse_ownership_table(BeautifulSoup(html, "lxml").find("table"))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["shares_before"], 11578308)
        self.assertEqual(row["shares_after"], 11578308)
        self.assertIsNone(row["percent"])
        self.assertIsNone(row["percent_before"])
        self.assertIsNone(row["percent_after"])

    def test_single_class_continuation_percent_does_not_leak_into_generic_percent(self):
        """A one-class continuation table cannot erase the wider table's class context."""
        html = """<table>
        <tr>
          <th>Name of beneficial owner</th>
          <th>Class B Common Stock beneficially owned after offering Shares</th>
          <th>Class B Common Stock beneficially owned after offering %</th>
        </tr>
        <tr><td>Thomas Hendrix (3)(9)</td><td>11,578,308</td><td>100</td></tr>
        </table>"""
        rows = parse_ownership_table(BeautifulSoup(html, "lxml").find("table"))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["shares_after"], 11578308)
        self.assertIsNone(row["percent"])
        self.assertIsNone(row["percent_after"])


if __name__ == "__main__":
    unittest.main()

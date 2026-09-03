import unittest

from bs4 import BeautifulSoup

from ownership_parser import parse_ownership_table


class OwnershipReorganizationBasisTests(unittest.TestCase):
    def test_predecessor_share_count_is_not_compared_to_multiclass_registrant_stock(self):
        html = """
        <table>
          <tr>
            <th>Name of beneficial owner</th>
            <th>Shares beneficially owned prior to the offering HMH B.V. ordinary shares Number</th>
            <th>Shares beneficially owned prior to the offering HMH B.V. ordinary shares %</th>
            <th>Shares beneficially owned after the offering Class A common stock Number</th>
            <th>Shares beneficially owned after the offering Class A common stock %</th>
            <th>Shares beneficially owned after the offering Class B common stock Number</th>
            <th>Shares beneficially owned after the offering Class B common stock %</th>
            <th>Shares beneficially owned after the offering Combined voting power Number</th>
            <th>Shares beneficially owned after the offering Combined voting power %</th>
          </tr>
          <tr>
            <td>Baker Hughes Holdings LLC</td>
            <td>100</td><td>50.0%</td>
            <td>—</td><td>0.0%</td>
            <td>16,288,748</td><td>37.0%</td>
            <td>99,999,999</td><td>37.0%</td>
          </tr>
        </table>
        """
        rows = parse_ownership_table(BeautifulSoup(html, "lxml").find("table"))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIsNone(row["shares_before"])
        self.assertEqual(row["percent_before"], 50.0)
        self.assertEqual(row["shares_after"], 16288748)
        # The 37% disclosures are Class B ownership / combined voting-power
        # percentages. Neither is a class-agnostic total-equity ownership percent.
        self.assertIsNone(row["percent_after"])

    def test_combined_voting_power_is_not_published_as_ownership(self):
        html = """
        <table>
          <tr>
            <th>Name of beneficial owner</th>
            <th>Combined voting power after the offering Number</th>
            <th>Combined voting power after the offering %</th>
          </tr>
          <tr><td>Example Holdings LLC</td><td>25,000,000</td><td>37.0%</td></tr>
        </table>
        """
        # A voting-power-only row has no supported generic ownership metric, so
        # the rich ownership parser must not publish either value as shares or %.
        self.assertEqual(
            parse_ownership_table(BeautifulSoup(html, "lxml").find("table")),
            [],
        )


if __name__ == "__main__":
    unittest.main()

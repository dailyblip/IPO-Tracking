import unittest

from bs4 import BeautifulSoup

from ownership_parser import parse_ownership_table


class GenericOwnershipLabelTests(unittest.TestCase):
    def test_other_aggregate_row_is_not_published_as_holder(self):
        html = """<table>
        <tr><th>Name of beneficial owner</th><th>Shares beneficially owned</th><th>Percent of class</th></tr>
        <tr><td>James Wang</td><td>1,243,291</td><td>6.22%</td></tr>
        <tr><td>Other</td><td>810,035</td><td>4.05%</td></tr>
        <tr><td>Other World Capital LLC</td><td>500,000</td><td>2.50%</td></tr>
        </table>"""

        rows = parse_ownership_table(BeautifulSoup(html, "lxml").find("table"))

        self.assertEqual(
            [row["name"] for row in rows],
            ["James Wang", "Other World Capital LLC"],
        )
        self.assertEqual(rows[0]["shares_after"], 1243291)
        self.assertEqual(rows[0]["percent_after"], 6.22)
        self.assertEqual(rows[1]["shares_after"], 500000)
        self.assertEqual(rows[1]["percent_after"], 2.50)


if __name__ == "__main__":
    unittest.main()

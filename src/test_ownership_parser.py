import unittest
from bs4 import BeautifulSoup
from ownership_parser import parse_ownership_table


class OwnershipParserTests(unittest.TestCase):
    def test_wide_before_sold_after_grid(self):
        html="""<table><tr><th>Name of beneficial owner</th><th colspan='2'>Beneficially owned before offering</th><th>Shares offered</th><th colspan='2'>Beneficially owned after offering</th></tr><tr><th></th><th>Number</th><th>Percent</th><th></th><th>Number</th><th>Percent</th></tr><tr><td>Jane Smith</td><td>1,000,000</td><td>10.0%</td><td>100,000</td><td>900,000</td><td>8.2%</td></tr></table>"""
        rows=parse_ownership_table(BeautifulSoup(html,'lxml').find('table'))
        self.assertEqual(len(rows),1)
        r=rows[0]
        self.assertEqual(r['shares_before'],1000000)
        self.assertEqual(r['shares_sold'],100000)
        self.assertEqual(r['shares_after'],900000)
        self.assertEqual(r['percent_before'],10.0)
        self.assertEqual(r['percent_after'],8.2)

    def test_prospectus_section_headings_are_not_beneficial_owners(self):
        html="""<table>
        <tr><th>Name of beneficial owner</th><th>Shares beneficially owned</th></tr>
        <tr><td>Jane Smith</td><td>1,000</td></tr>
        <tr><td>DESCRIPTION OF CAPITAL STOCK</td><td>123</td></tr>
        <tr><td>SHARES ELIGIBLE FOR FUTURE SALE</td><td>132</td></tr>
        <tr><td>MATERIAL U.S. FEDERAL INCOME TAX CONSIDERATIONS</td><td>134</td></tr>
        <tr><td>UNDERWRITING (CONFLICTS OF INTEREST)</td><td>138</td></tr>
        <tr><td>LEGAL MATTERS</td><td>147</td></tr>
        </table>"""
        rows=parse_ownership_table(BeautifulSoup(html,'lxml').find('table'))
        self.assertEqual([row['name'] for row in rows], ['Jane Smith'])

    def test_uppercase_corporate_owner_is_preserved(self):
        html="""<table>
        <tr><th>Name of beneficial owner</th><th>Shares beneficially owned</th></tr>
        <tr><td>IBM CORPORATION</td><td>5,000</td></tr>
        </table>"""
        rows=parse_ownership_table(BeautifulSoup(html,'lxml').find('table'))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'IBM CORPORATION')
        self.assertEqual(rows[0]['shares_after'], 5000)


class HolderIdentityQaTests(unittest.TestCase):
    def test_canonical_holder_name_strips_sec_dot_leaders(self):
        import ownership_parser
        self.assertEqual(ownership_parser.canonical_holder_name("Gwynne Shotwell..................."), "gwynne shotwell")
        self.assertEqual(ownership_parser.canonical_holder_name("Gwynne Shotwell (12)"), "gwynne shotwell")


if __name__=='__main__':
    unittest.main()

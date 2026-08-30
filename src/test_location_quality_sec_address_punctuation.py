import unittest

from bs4 import BeautifulSoup

import location_quality


class SecFilingAddressPunctuationTests(unittest.TestCase):
    def test_yesway_style_comma_delimited_principal_office(self):
        soup = BeautifulSoup(
            """
            <html><body>
            Yesway, Inc.
            2301 Eagle Parkway, Fort Worth, TX 76177
            (Address, including zip code, and telephone number, including area code,
            of registrant's principal executive offices)
            </body></html>
            """,
            "html.parser",
        )

        self.assertEqual(
            location_quality._extract_filing_principal_office_location(soup),
            "Fort Worth, TX",
        )

    def test_comma_after_suite_is_supported(self):
        soup = BeautifulSoup(
            """
            <html><body>
            2301 Eagle Parkway, Suite 100, Fort Worth, TX 76177
            (Address, including zip code, and telephone number, including area code,
            of registrant's principal executive offices)
            </body></html>
            """,
            "html.parser",
        )

        self.assertEqual(
            location_quality._extract_filing_principal_office_location(soup),
            "Fort Worth, TX",
        )


if __name__ == "__main__":
    unittest.main()

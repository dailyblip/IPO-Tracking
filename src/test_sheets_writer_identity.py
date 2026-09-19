import unittest

from sheets_writer import _row_key


class SheetRowIdentityTests(unittest.TestCase):
    def test_same_blank_ticker_and_holder_do_not_collide_across_issuers(self):
        first = {
            "Company Name": "Issuer One, Inc.",
            "Ticker": "",
            "Holder Name": "Shared Fund LP",
        }
        second = {
            "Company Name": "Issuer Two, Inc.",
            "Ticker": "",
            "Holder Name": "Shared Fund LP",
        }

        self.assertNotEqual(_row_key(first), _row_key(second))

    def test_reused_ticker_and_holder_do_not_collide_across_issuers(self):
        first = {
            "Company Name": "Legacy Operating Co.",
            "Ticker": "ABCD",
            "Holder Name": "Common Sponsor LLC",
        }
        second = {
            "Company Name": "New Operating Co.",
            "Ticker": "ABCD",
            "Holder Name": "Common Sponsor LLC",
        }

        self.assertNotEqual(_row_key(first), _row_key(second))

    def test_identity_normalizes_case_and_whitespace(self):
        canonical = {
            "Company Name": "Example Holdings, Inc.",
            "Ticker": "EXM",
            "Holder Name": "Jane Example",
        }
        variant = {
            "Company Name": "  EXAMPLE   HOLDINGS, INC. ",
            "Ticker": " exm ",
            "Holder Name": " JANE   EXAMPLE ",
        }

        self.assertEqual(_row_key(canonical), _row_key(variant))


if __name__ == "__main__":
    unittest.main()

import unittest

from edgar_client import SPAC_NAME_PATTERN
from public_feed_policy import qualifies_for_public_feed


class RmgSpacReleaseGateTests(unittest.TestCase):
    def test_rmg_ml_sports_holdings_is_excluded(self):
        filing = {
            "company": "RMG ML Sports Holdings",
            "form": "424B4",
            "value": None,
        }
        self.assertIsNotNone(SPAC_NAME_PATTERN.search(filing["company"]))
        self.assertFalse(qualifies_for_public_feed(filing))

    def test_generic_operating_holdings_name_remains_eligible(self):
        filing = {
            "company": "Acme Industrial Holdings, Inc.",
            "form": "424B4",
            "value": 75_000_000,
        }
        self.assertIsNone(SPAC_NAME_PATTERN.search(filing["company"]))
        self.assertTrue(qualifies_for_public_feed(filing))


if __name__ == "__main__":
    unittest.main()

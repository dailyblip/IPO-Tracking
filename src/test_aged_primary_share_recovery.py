import unittest
from datetime import date

from offering_value_reconciler import _needs_check


class AgedPrimaryShareRecoveryTests(unittest.TestCase):
    def test_aged_priced_row_with_blank_primary_shares_still_gets_sec_recovery_attempt(self):
        filing = {
            "form": "424B4",
            "stage": "Priced",
            "pricing_date": "2026-07-23",
            "value": 128_700_000,
            "primary_offering_shares": None,
        }

        self.assertTrue(_needs_check(filing, today=date(2026, 9, 7)))

    def test_aged_complete_whole_dollar_row_can_skip_refetch(self):
        filing = {
            "form": "424B4",
            "stage": "Priced",
            "pricing_date": "2026-07-23",
            "value": 128_700_000,
            "primary_offering_shares": 8_580_000,
        }

        self.assertFalse(_needs_check(filing, today=date(2026, 9, 7)))


if __name__ == "__main__":
    unittest.main()

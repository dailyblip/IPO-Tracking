import unittest

from main import _holder_share_positions


class HolderSharePositionTests(unittest.TestCase):
    def test_missing_after_position_is_not_inferred_from_before_minus_sold(self):
        holder = {
            "shares_before": 27_648_856,
            "shares_sold": 3_033_209,
            "shares_after": None,
            "shares": None,
        }

        before, sold, after, shares = _holder_share_positions(holder)

        self.assertEqual(before, 27_648_856)
        self.assertEqual(sold, 3_033_209)
        self.assertIsNone(after)
        self.assertIsNone(shares)
        self.assertNotEqual(after, 24_615_647)

    def test_authoritative_after_position_is_preserved(self):
        holder = {
            "shares_before": 1_000,
            "shares_sold": 100,
            "shares_after": 875,
            "shares": 875,
        }

        before, sold, after, shares = _holder_share_positions(holder)

        self.assertEqual((before, sold, after, shares), (1_000, 100, 875, 875))

    def test_generic_reported_share_count_remains_available_when_after_is_absent(self):
        holder = {
            "shares_before": None,
            "shares_sold": None,
            "shares_after": None,
            "shares": 42_000,
        }

        before, sold, after, shares = _holder_share_positions(holder)

        self.assertIsNone(before)
        self.assertIsNone(sold)
        self.assertIsNone(after)
        self.assertEqual(shares, 42_000)


if __name__ == "__main__":
    unittest.main()

import math
import unittest

from price_lookup import (
    MAX_FUTURE_SKEW_SECONDS,
    MAX_QUOTE_AGE_SECONDS,
    PriceLookupError,
    _validate_quote,
)


class PriceLookupValidationTests(unittest.TestCase):
    def test_accepts_recent_positive_quote(self):
        now = 2_000_000_000
        self.assertEqual(
            _validate_quote("TEST", {"c": 42.5, "t": now - 60}, now=now),
            42.5,
        )

    def test_rejects_quote_older_than_freshness_window(self):
        now = 2_000_000_000
        with self.assertRaisesRegex(PriceLookupError, "stale data"):
            _validate_quote(
                "TEST",
                {"c": 42.5, "t": now - MAX_QUOTE_AGE_SECONDS - 1},
                now=now,
            )

    def test_rejects_missing_quote_timestamp(self):
        with self.assertRaisesRegex(PriceLookupError, "missing a valid timestamp"):
            _validate_quote("TEST", {"c": 42.5}, now=2_000_000_000)

    def test_rejects_quote_timestamp_too_far_in_future(self):
        now = 2_000_000_000
        with self.assertRaisesRegex(PriceLookupError, "timestamp in the future"):
            _validate_quote(
                "TEST",
                {"c": 42.5, "t": now + MAX_FUTURE_SKEW_SECONDS + 1},
                now=now,
            )

    def test_rejects_non_positive_or_non_finite_price(self):
        now = 2_000_000_000
        for bad_price in (0, -1, math.nan, math.inf):
            with self.subTest(price=bad_price):
                with self.assertRaises(PriceLookupError):
                    _validate_quote("TEST", {"c": bad_price, "t": now - 60}, now=now)


if __name__ == "__main__":
    unittest.main()

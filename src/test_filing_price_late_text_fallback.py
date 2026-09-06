import unittest

import filing_price_history


class FilingPriceLateTextFallbackTests(unittest.TestCase):
    def test_range_after_old_cutoff_is_recovered(self):
        text = (
            ("Risk factors and business discussion. " * 2500)
            + "It is currently estimated that the initial public offering price per share "
            + "will be between $18.00 and $20.00."
        )
        self.assertGreater(text.index("initial public offering price"), 60000)
        self.assertEqual(
            filing_price_history._extract_explicit_price_range_from_text(text),
            {"range_low": 18.0, "range_high": 20.0},
        )

    def test_fixed_price_after_old_cutoff_is_recovered(self):
        text = (
            ("Risk factors and business discussion. " * 2500)
            + "We expect the initial public offering price to be $17.00 per share."
        )
        self.assertGreater(text.index("initial public offering price"), 60000)
        self.assertEqual(
            filing_price_history._extract_explicit_price_range_from_text(text),
            {"range_low": 17.0, "range_high": 17.0},
        )


if __name__ == "__main__":
    unittest.main()

import os
import unittest

os.environ.setdefault("SEC_EDGAR_USER_AGENT", "Research Monitor test@example.com")

import s1_preliminary_price_gate as gate


FILLER = "Background disclosure without pricing terms. " * 1000


class DistantConversionPointPriceTests(unittest.TestCase):
    def test_distant_conversion_price_requires_and_accepts_explicit_ipo_context(self):
        text = (
            "This is our initial public offering of common stock. "
            + FILLER
            + "The purchase price of each share of common stock to be sold in the "
            "stock offering is $10.00."
        )

        self.assertGreater(len(text), gate.COVER_TEXT_LIMIT)
        self.assertEqual(gate._extract_authoritative_proposed_point_price(text), 10.0)

    def test_distant_conversion_price_without_ipo_context_is_rejected(self):
        text = (
            "Registration statement for a stock offering. "
            + FILLER
            + "The purchase price of each share of common stock to be sold in the "
            "stock offering is $10.00."
        )

        self.assertGreater(len(text), gate.COVER_TEXT_LIMIT)
        self.assertIsNone(gate._extract_authoritative_proposed_point_price(text))

    def test_distant_generic_point_price_remains_cover_bounded(self):
        text = (
            "This is our initial public offering of common stock. "
            + FILLER
            + "The initial public offering price per share is to be fixed at "
            "$11.00 per share."
        )

        self.assertGreater(len(text), gate.COVER_TEXT_LIMIT)
        self.assertIsNone(gate._extract_authoritative_proposed_point_price(text))


if __name__ == "__main__":
    unittest.main()

import unittest

from market_quote_identity import QuoteIdentityError, _company_names_match, _validate_profile


class MarketQuoteBrandSuffixIdentityTests(unittest.TestCase):
    def test_only_recognized_sec_jurisdiction_suffixes_are_ignored(self):
        self.assertTrue(_company_names_match("Example Corp./DE/", "Example Corporation"))
        self.assertTrue(_company_names_match("Example Corp / NV", "Example Corporation"))
        self.assertFalse(_company_names_match("Example/AI", "Example"))
        self.assertFalse(_company_names_match("Example/UK", "Example"))
        self.assertTrue(_company_names_match("Example/AI", "Example/AI"))

    def test_quote_gate_rejects_provider_name_that_drops_brand_suffix(self):
        with self.assertRaisesRegex(QuoteIdentityError, "possibly collided quote"):
            _validate_profile(
                "EXAI",
                "Example/AI",
                {"ticker": "EXAI", "name": "Example"},
            )


if __name__ == "__main__":
    unittest.main()

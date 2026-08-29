import unittest

import edgar_client


class ResaleRegistrationExclusionTests(unittest.TestCase):
    def test_fullpac_style_resale_registration_is_excluded(self):
        filing_text = (
            "Preliminary Prospectus. 3,915,995 Shares of Common Stock. "
            "This prospectus relates to the offer and sale, from time to time, "
            "by the selling securityholders named in this prospectus or their "
            "permitted transferees of an aggregate of 3,915,995 shares."
        )
        self.assertTrue(edgar_client.check_direct_listing_indicators(filing_text))

    def test_primary_ipo_with_secondary_shares_is_not_misclassified(self):
        filing_text = (
            "We are offering 8,000,000 shares of common stock and the selling "
            "stockholders are offering 2,000,000 shares. We will not receive "
            "proceeds from shares sold by the selling stockholders."
        )
        self.assertFalse(edgar_client.check_direct_listing_indicators(filing_text))

    def test_generic_resale_risk_factor_does_not_trigger(self):
        filing_text = (
            "This is our initial public offering. No public market currently exists. "
            "Future resales by stockholders could adversely affect the market price."
        )
        self.assertFalse(edgar_client.check_direct_listing_indicators(filing_text))


if __name__ == "__main__":
    unittest.main()

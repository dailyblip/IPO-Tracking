import unittest

import edgar_client


class ResalePunctuationRegressionTests(unittest.TestCase):
    def test_fullpac_resale_phrase_tolerates_inline_xbrl_punctuation_spacing(self):
        filing_text = (
            "Preliminary Prospectus. 3,915,995 Shares of Common Stock. "
            "This prospectus relates to the offer and sale , from time to time , "
            "by the selling securityholders named in this prospectus or their "
            "permitted transferees of an aggregate of 3,915,995 shares."
        )
        self.assertTrue(edgar_client.check_direct_listing_indicators(filing_text))

    def test_primary_ipo_secondary_component_remains_allowed(self):
        filing_text = (
            "This is our initial public offering. We are offering 8,000,000 shares "
            "and the selling stockholders are offering 2,000,000 shares. We will "
            "not receive proceeds from shares sold by the selling stockholders."
        )
        self.assertFalse(edgar_client.check_direct_listing_indicators(filing_text))


if __name__ == "__main__":
    unittest.main()

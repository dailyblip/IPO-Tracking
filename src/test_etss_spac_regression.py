import unittest

import edgar_client


class IssuerAnchoredSpacSelfDescriptionTests(unittest.TestCase):
    def test_etss_style_named_blank_check_self_description_is_excluded(self):
        text = (
            "Energy Transition Special Opportunities is a blank check company "
            "incorporated as a Cayman Islands exempted company for the purpose of "
            "effecting a merger, share exchange, asset acquisition, share purchase, "
            "reorganization or similar business combination."
        )

        self.assertTrue(
            edgar_client.check_spac_indicators(
                text,
                company_name="Energy Transition Special Opportunities",
            )
        )

    def test_third_party_blank_check_reference_does_not_exclude_operating_issuer(self):
        text = (
            "Operating Co. is a commercial software company. "
            "In market-risk discussion, Example Acquisition Corp is a blank check company."
        )

        self.assertFalse(
            edgar_client.check_spac_indicators(
                text,
                company_name="Operating Co.",
            )
        )


if __name__ == "__main__":
    unittest.main()

import unittest

from public_feed_policy import qualifies_for_public_feed


class ReleaseNameSafeguardTests(unittest.TestCase):
    def test_explicit_exchange_traded_products_are_excluded(self):
        excluded = (
            "Example ETF Trust",
            "Example ETN Notes",
            "Example Exchange-Traded Fund",
            "Example Exchange Traded Note",
        )
        for company in excluded:
            with self.subTest(company=company):
                self.assertFalse(
                    qualifies_for_public_feed(
                        {"company": company, "form": "424B4", "value": 500_000_000}
                    )
                )

    def test_generic_trust_word_is_not_an_automatic_exclusion(self):
        # "Trust" by itself is not reliable evidence that an issuer is a pooled
        # investment vehicle. Product classification must remain evidence-based.
        self.assertTrue(
            qualifies_for_public_feed(
                {"company": "Acme Trust Services, Inc.", "form": "424B4", "value": 250_000_000}
            )
        )

    def test_generic_holdings_word_is_not_an_automatic_exclusion(self):
        self.assertTrue(
            qualifies_for_public_feed(
                {"company": "Acme Holdings, Inc.", "form": "424B4", "value": 250_000_000}
            )
        )


if __name__ == "__main__":
    unittest.main()

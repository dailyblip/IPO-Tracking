import unittest

from person_economic_attribution_guard import suppress_unsupported_person_economics


class HolderRealizedCashPolicyTests(unittest.TestCase):
    def test_public_offer_price_does_not_become_holder_realized_cash(self):
        filing = {
            "cik": "0002132582",
            "accession_no": "0001193125-26-356916",
            "company": "Lyntris Inc.",
            "people": [
                {
                    "name": "Example Selling Stockholder",
                    "shares_before_ipo": 1_000,
                    "shares_sold_ipo": 100,
                    "shares_after_ipo": 900,
                    "shares": 900,
                    "cash_realized_ipo": 1_750.0,
                    "cash_value": 12_600.0,
                }
            ],
        }

        normalized = suppress_unsupported_person_economics(filing)
        person = normalized["people"][0]

        # Keep the SEC-supported sale quantity, but do not claim the holder realized
        # public offering price x shares sold. Underwriting discounts/commissions can
        # make actual proceeds lower unless holder-level proceeds are explicitly sourced.
        self.assertEqual(person["shares_sold_ipo"], 100)
        self.assertIsNone(person["cash_realized_ipo"])
        self.assertEqual(person["shares_after_ipo"], 900)
        self.assertEqual(person["cash_value"], 12_600.0)


if __name__ == "__main__":
    unittest.main()

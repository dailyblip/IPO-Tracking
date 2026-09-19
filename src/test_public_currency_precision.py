import unittest

from prepricing_quote_sanitizer import sanitize_payload


class PublicCurrencyPrecisionTests(unittest.TestCase):
    def test_normalizes_holder_currency_without_rounding_per_share_quote(self):
        payload = {
            "filings": [{
                "id": "priced-currency-precision",
                "form": "424B4",
                "stage": "Priced",
                "filed": "2026-08-27",
                "pricing_date": "2026-08-26",
                "offering_price": 17.5,
                "current_price": 13.6917,
                "price_updated": "2026-08-27T20:05:29+00:00",
                "people": [{
                    "name": "Example Holder",
                    "shares": 1_260_126,
                    "cash_value": 17_251_124.939999998,
                    "ipo_value": 22_052_205.000000004,
                    "liquid_value": 5_788_734.359999999,
                    "locked_value": 4_906_386.4799999995,
                    "cash_realized_ipo": 123_456.78999999998,
                }],
            }]
        }

        sanitized, changed = sanitize_payload(payload)
        filing = sanitized["filings"][0]
        person = filing["people"][0]

        self.assertEqual(changed, 1)
        self.assertEqual(filing["current_price"], 13.6917)
        self.assertEqual(filing["offering_price"], 17.5)
        self.assertEqual(person["shares"], 1_260_126)
        self.assertEqual(person["cash_value"], 17_251_124.94)
        self.assertEqual(person["ipo_value"], 22_052_205.0)
        self.assertEqual(person["liquid_value"], 5_788_734.36)
        self.assertEqual(person["locked_value"], 4_906_386.48)
        self.assertEqual(person["cash_realized_ipo"], 123_456.79)

    def test_unsafe_quote_still_preserves_and_normalizes_ipo_currency(self):
        payload = {
            "filings": [{
                "id": "prepricing-currency-precision",
                "form": "S-1/A",
                "stage": "Pre-pricing",
                "current_price": 13.6917,
                "price_updated": "2026-08-27T20:05:29+00:00",
                "people": [{
                    "name": "Example Holder",
                    "cash_value": 17_251_124.939999998,
                    "ipo_value": 22_052_205.000000004,
                    "cash_realized_ipo": 123_456.78999999998,
                }],
            }]
        }

        sanitized, changed = sanitize_payload(payload)
        filing = sanitized["filings"][0]
        person = filing["people"][0]

        self.assertEqual(changed, 1)
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertNotIn("cash_value", person)
        self.assertEqual(person["ipo_value"], 22_052_205.0)
        self.assertEqual(person["cash_realized_ipo"], 123_456.79)


if __name__ == "__main__":
    unittest.main()

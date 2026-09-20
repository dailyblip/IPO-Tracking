import unittest

from prepricing_quote_sanitizer import sanitize_payload


class PrepricingQuoteTickerProvenanceTests(unittest.TestCase):
    def test_final_ipo_with_blank_ticker_cannot_publish_current_price(self):
        payload = {
            "filings": [
                {
                    "id": "blank-ticker-final",
                    "company": "Example Operating Co",
                    "ticker": " ",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-09-18",
                    "pricing_date": "2026-09-17",
                    "offering_price": 15.0,
                    "current_price": 13.25,
                    "price_updated": "2026-09-18T20:00:00+00:00",
                    "signals": [
                        "Offering priced at $15.00 per share",
                        "Largest named holding currently valued at approximately $5M",
                    ],
                    "people": [
                        {
                            "name": "Example Holder",
                            "shares": 400_000,
                            "cash_value": 5_300_000,
                            "valuation_as_of": "2026-09-18",
                        }
                    ],
                }
            ]
        }

        sanitized, changed = sanitize_payload(payload)

        self.assertEqual(changed, 1)
        filing = sanitized["filings"][0]
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertEqual(filing["signals"], ["Offering priced at $15.00 per share"])
        self.assertNotIn("cash_value", filing["people"][0])
        self.assertNotIn("valuation_as_of", filing["people"][0])


if __name__ == "__main__":
    unittest.main()

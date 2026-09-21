import copy
import unittest

import prepricing_quote_sanitizer


class PrepricingFinalMetadataSanitizerTests(unittest.TestCase):
    def test_genuine_prepricing_row_loses_stale_final_metadata_but_keeps_filing_price(self):
        filing_price_source = {
            "source": "SEC EDGAR",
            "form": "S-1/A",
            "filing_date": "2026-09-18",
            "accession_no": "0000000000-26-000001",
            "sec_url": "https://www.sec.gov/Archives/edgar/data/1/000000000026000001/example.htm",
        }
        payload = {
            "filings": [
                {
                    "id": "example-prepricing",
                    "company": "Example Systems Inc.",
                    "ticker": "EXMP",
                    "form": "S-1/A",
                    "stage": "Pre-pricing",
                    "filed": "2026-09-18",
                    "filing_price": "$15–$17",
                    "price_range": "$15–$17",
                    "filing_price_source": copy.deepcopy(filing_price_source),
                    "offering_price": 16.0,
                    "current_price": 28.5,
                    "price_updated": "2026-09-20T16:00:00+00:00",
                    "signals": [
                        "Offering priced at $16 per share",
                        "Offering raised approximately $160 million",
                        "Largest named holding currently valued at approximately $28.5 million",
                        "10 named beneficial owners disclosed",
                    ],
                    "people": [
                        {
                            "name": "Example Holder",
                            "shares": 1_000_000,
                            "shares_sold_ipo": 100_000,
                            "ipo_value": 16_000_000,
                            "cash_realized_ipo": 1_600_000,
                            "cash_value": 28_500_000,
                            "liquid_value": 2_850_000,
                            "locked_value": 25_650_000,
                            "valuation_as_of": "2026-09-20T16:00:00+00:00",
                        }
                    ],
                }
            ]
        }

        sanitized, changed = prepricing_quote_sanitizer.sanitize_payload(payload)
        filing = sanitized["filings"][0]
        person = filing["people"][0]

        self.assertEqual(changed, 1)
        self.assertEqual(filing["filing_price"], "$15–$17")
        self.assertEqual(filing["price_range"], "$15–$17")
        self.assertEqual(filing["filing_price_source"], filing_price_source)
        self.assertNotIn("offering_price", filing)
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertEqual(filing["signals"], ["10 named beneficial owners disclosed"])
        self.assertEqual(person["shares"], 1_000_000)
        self.assertEqual(person["shares_sold_ipo"], 100_000)
        for field in (
            "ipo_value",
            "cash_realized_ipo",
            "cash_value",
            "liquid_value",
            "locked_value",
            "valuation_as_of",
        ):
            self.assertNotIn(field, person)

    def test_valid_priced_424b4_keeps_final_price_and_final_price_derivatives(self):
        payload = {
            "filings": [
                {
                    "id": "example-final",
                    "company": "Example Systems Inc.",
                    "ticker": "EXMP",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-09-20",
                    "pricing_date": "2026-09-20",
                    "offering_price": 18.0,
                    "current_price": 19.0,
                    "price_updated": "2026-09-20T20:00:00+00:00",
                    "signals": ["Offering priced at $18 per share"],
                    "people": [
                        {
                            "name": "Example Holder",
                            "shares": 1_000,
                            "shares_sold_ipo": 100,
                            "ipo_value": 18_000,
                            "cash_realized_ipo": 1_800,
                        }
                    ],
                }
            ]
        }

        sanitized, changed = prepricing_quote_sanitizer.sanitize_payload(payload)
        filing = sanitized["filings"][0]
        person = filing["people"][0]

        self.assertEqual(changed, 0)
        self.assertEqual(filing["offering_price"], 18.0)
        self.assertEqual(filing["current_price"], 19.0)
        self.assertEqual(person["ipo_value"], 18_000)
        self.assertEqual(person["cash_realized_ipo"], 1_800)
        self.assertEqual(filing["signals"], ["Offering priced at $18 per share"])

    def test_ambiguous_s1_stage_is_not_silently_repaired_as_prepricing(self):
        payload = {
            "filings": [
                {
                    "id": "ambiguous-s1",
                    "company": "Example Systems Inc.",
                    "ticker": "EXMP",
                    "form": "S-1",
                    "stage": "Priced",
                    "filed": "2026-09-18",
                    "offering_price": 16.0,
                    "people": [{"name": "Example Holder", "ipo_value": 16_000}],
                    "signals": ["Offering priced at $16 per share"],
                }
            ]
        }

        sanitized, _ = prepricing_quote_sanitizer.sanitize_payload(payload)
        filing = sanitized["filings"][0]

        self.assertEqual(filing["offering_price"], 16.0)
        self.assertEqual(filing["people"][0]["ipo_value"], 16_000)
        self.assertEqual(filing["signals"], ["Offering priced at $16 per share"])


if __name__ == "__main__":
    unittest.main()

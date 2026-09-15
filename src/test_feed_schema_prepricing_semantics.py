import unittest

from feed_schema_contract import validate_payload


class FeedSchemaPrepricingSemanticTests(unittest.TestCase):
    def _filing(self, **updates):
        filing = {
            "id": "prepricing-example",
            "company": "Example Robotics, Inc.",
            "ticker": "EXRB",
            "cik": "0001234567",
            "accession_no": "0001193125-26-123456",
            "form": "S-1/A",
            "filed": "2026-08-20",
            "filing_date": "2026-08-18",
            "pricing_date": None,
            "stage": "Pre-pricing",
            "priority": "Medium",
            "status": "New",
            "value": None,
            "value_label": None,
            "people_count": 0,
            "signals": [],
            "people": [],
            "sec_url": (
                "https://www.sec.gov/Archives/edgar/data/1234567/"
                "000119312526123456/example-s1a.htm"
            ),
            "offering_price": None,
            "current_price": None,
            "price_updated": None,
        }
        filing.update(updates)
        return filing

    def _payload(self, filing):
        return {
            "schema_version": 1,
            "generated_at": "2026-09-15T19:00:00+00:00",
            "source": "SEC EDGAR",
            "filings": [filing],
        }

    def test_clean_prepricing_row_matches_v1_schema(self):
        self.assertEqual([], validate_payload(self._payload(self._filing())))

    def test_prepricing_pricing_date_is_schema_blocking(self):
        failures = validate_payload(
            self._payload(self._filing(pricing_date="2026-08-24"))
        )
        self.assertTrue(failures)
        self.assertTrue(any("pricing_date" in failure for failure in failures), failures)

    def test_prepricing_final_ipo_price_is_schema_blocking(self):
        failures = validate_payload(self._payload(self._filing(offering_price=18.0)))
        self.assertTrue(failures)
        self.assertTrue(any("offering_price" in failure for failure in failures), failures)


if __name__ == "__main__":
    unittest.main()

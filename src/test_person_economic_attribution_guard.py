import unittest

from person_economic_attribution_guard import suppress_unsupported_person_economics


class PersonEconomicAttributionGuardTests(unittest.TestCase):
    def test_disclaimed_indirect_position_keeps_shares_but_suppresses_personal_economics(self):
        filing = {
            "cik": "0001181412",
            "accession_no": "0001628280-26-042639",
            "company": "Space Exploration Technologies Corp",
            "signals": [
                "Largest named holding currently valued at approximately $70.8B",
                "Offering raised approximately $75.0B",
            ],
            "people": [
                {
                    "name": "Antonio J. Gracias",
                    "shares": 503_414_530,
                    "shares_after_ipo": 503_414_530,
                    "cash_value": 70_835_458_516.30,
                    "ipo_value": 67_960_961_550.0,
                    "liquid_shares": 10,
                    "liquid_value": 1_407.10,
                    "locked_shares": 503_414_520,
                    "locked_value": 70_835_457_109.20,
                    "cash_realized_ipo": 1_000_000.0,
                    "valuation_as_of": "2026-09-03",
                    "is_beneficial_owner": True,
                },
                {
                    "name": "Supported Holder",
                    "shares": 1_000_000,
                    "cash_value": 140_710_000.0,
                    "ipo_value": 135_000_000.0,
                },
            ],
        }

        normalized = suppress_unsupported_person_economics(filing)
        person = normalized["people"][0]

        # The SEC beneficial-ownership quantity remains a disclosed fact. What is
        # unsupported is attributing the full Valor-entity position economically
        # to the reporting person after the Form 3 disclaimer.
        self.assertEqual(person["shares"], 503_414_530)
        self.assertEqual(person["shares_after_ipo"], 503_414_530)
        self.assertTrue(person["is_beneficial_owner"])
        for field in (
            "cash_value",
            "ipo_value",
            "liquid_shares",
            "liquid_value",
            "locked_shares",
            "locked_value",
            "cash_realized_ipo",
            "valuation_as_of",
        ):
            self.assertIsNone(person[field], field)

        self.assertEqual(normalized["people"][1]["cash_value"], 140_710_000.0)
        self.assertEqual(
            normalized["signals"][0],
            "Largest named holding currently valued at approximately $141M",
        )
        self.assertIn("Offering raised approximately $75.0B", normalized["signals"])

    def test_exception_does_not_apply_when_authoritative_share_count_changes(self):
        filing = {
            "cik": "0001181412",
            "accession_no": "0001628280-26-042639",
            "people": [
                {
                    "name": "Antonio J. Gracias",
                    "shares": 1_000,
                    "cash_value": 140_710.0,
                    "ipo_value": 135_000.0,
                }
            ],
        }

        normalized = suppress_unsupported_person_economics(filing)
        self.assertEqual(normalized["people"][0]["cash_value"], 140_710.0)
        self.assertEqual(normalized["people"][0]["ipo_value"], 135_000.0)

    def test_same_name_other_issuer_is_untouched(self):
        filing = {
            "cik": "0000000001",
            "accession_no": "0000000001-26-000001",
            "people": [
                {
                    "name": "Antonio J. Gracias",
                    "shares": 503_414_530,
                    "cash_value": 1_000.0,
                }
            ],
        }

        normalized = suppress_unsupported_person_economics(filing)
        self.assertEqual(normalized["people"][0]["cash_value"], 1_000.0)


if __name__ == "__main__":
    unittest.main()

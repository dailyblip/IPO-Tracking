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

    def test_blossomhill_orbimed_disclaimer_suppresses_personal_fund_economics(self):
        filing = {
            "cik": "0001839970",
            "accession_no": "0001193125-26-340215",
            "company": "BlossomHill Therapeutics, Inc.",
            "people": [
                {
                    "name": "Carl L. Gordon, Ph.D., CFA",
                    "shares": 2_089_279,
                    "shares_before_ipo": 2_089_279,
                    "shares_after_ipo": 2_089_279,
                    "cash_value": 40_490_227.02,
                    "ipo_value": 33_428_464.0,
                    "locked_shares": 2_089_279,
                    "locked_value": 40_490_227.02,
                    "valuation_as_of": "2026-09-03",
                    "is_beneficial_owner": True,
                }
            ],
        }

        normalized = suppress_unsupported_person_economics(filing)
        person = normalized["people"][0]

        self.assertEqual(person["shares"], 2_089_279)
        self.assertEqual(person["shares_before_ipo"], 2_089_279)
        self.assertEqual(person["shares_after_ipo"], 2_089_279)
        self.assertTrue(person["is_beneficial_owner"])
        for field in (
            "cash_value",
            "ipo_value",
            "locked_shares",
            "locked_value",
            "valuation_as_of",
        ):
            self.assertIsNone(person[field], field)

    def test_blossomhill_household_aggregate_suppresses_duplicate_person_economics(self):
        filing = {
            "cik": "0001839970",
            "accession_no": "0001193125-26-340215",
            "company": "BlossomHill Therapeutics, Inc.",
            "people": [
                {
                    "name": "J. Jean Cui, Ph.D.",
                    "shares": 3_973_138,
                    "shares_before_ipo": 3_973_138,
                    "shares_after_ipo": 3_973_138,
                    "cash_value": 78_310_549.98,
                    "ipo_value": 63_570_208.0,
                    "locked_shares": 3_973_138,
                    "locked_value": 78_310_549.98,
                    "valuation_as_of": "2026-09-03",
                    "is_beneficial_owner": True,
                },
                {
                    "name": "Y. Peter Li, Ph.D., MBA",
                    "shares": 3_973_138,
                    "shares_before_ipo": 3_973_138,
                    "shares_after_ipo": 3_973_138,
                    "cash_value": 78_310_549.98,
                    "ipo_value": 63_570_208.0,
                    "locked_shares": 3_973_138,
                    "locked_value": 78_310_549.98,
                    "valuation_as_of": "2026-09-03",
                    "is_beneficial_owner": True,
                },
                {
                    "name": "J. Jean Cui, Ph.D. and Y. Peter Li, Ph.D., MBA and related affiliates",
                    "shares": 3_973_138,
                    "cash_value": 78_310_549.98,
                    "ipo_value": 63_570_208.0,
                },
            ],
        }

        normalized = suppress_unsupported_person_economics(filing)

        for person in normalized["people"][:2]:
            self.assertTrue(person["is_beneficial_owner"])
            self.assertEqual(person["shares"], 3_973_138)
            self.assertEqual(person["shares_before_ipo"], 3_973_138)
            self.assertEqual(person["shares_after_ipo"], 3_973_138)
            for field in (
                "cash_value",
                "ipo_value",
                "locked_shares",
                "locked_value",
                "valuation_as_of",
            ):
                self.assertIsNone(person[field], f"{person['name']} {field}")

        # The combined household/affiliate record remains evidence-supported and is
        # the correct place to retain the aggregate economic value.
        self.assertEqual(normalized["people"][2]["cash_value"], 78_310_549.98)
        self.assertEqual(normalized["people"][2]["ipo_value"], 63_570_208.0)

    def test_latigo_vc_disclaimers_suppress_personal_fund_economics(self):
        filing = {
            "cik": "0002056611",
            "accession_no": "0001193125-26-340329",
            "company": "Latigo Biotherapeutics, Inc.",
            "signals": ["Largest named holding currently valued at approximately $287M"],
            "people": [
                {
                    "name": "Beth Seidenberg, M.D.",
                    "shares": 13_199_669,
                    "shares_before_ipo": 13_199_669,
                    "shares_after_ipo": 13_199_669,
                    "cash_value": 287_356_794.13,
                    "ipo_value": 237_594_042.0,
                    "locked_shares": 13_199_669,
                    "locked_value": 287_356_794.13,
                    "valuation_as_of": "2026-09-03",
                    "is_beneficial_owner": True,
                },
                {
                    "name": "James B. Tananbaum, M.D.",
                    "shares": 9_041_328,
                    "shares_before_ipo": 9_041_328,
                    "shares_after_ipo": 9_041_328,
                    "cash_value": 196_829_710.56,
                    "ipo_value": 162_743_904.0,
                    "locked_shares": 9_041_328,
                    "locked_value": 196_829_710.56,
                    "valuation_as_of": "2026-09-03",
                    "is_beneficial_owner": True,
                },
                {
                    "name": "Supported Holder",
                    "shares": 3_000_000,
                    "cash_value": 65_310_000.0,
                    "ipo_value": 54_000_000.0,
                },
            ],
        }

        normalized = suppress_unsupported_person_economics(filing)

        for person in normalized["people"][:2]:
            self.assertTrue(person["is_beneficial_owner"])
            self.assertIsNotNone(person["shares"])
            self.assertIsNotNone(person["shares_before_ipo"])
            self.assertIsNotNone(person["shares_after_ipo"])
            for field in (
                "cash_value",
                "ipo_value",
                "locked_shares",
                "locked_value",
                "valuation_as_of",
            ):
                self.assertIsNone(person[field], f"{person['name']} {field}")

        self.assertEqual(normalized["people"][2]["cash_value"], 65_310_000.0)
        self.assertEqual(
            normalized["signals"],
            ["Largest named holding currently valued at approximately $65M"],
        )

    def test_scribe_fund_disclaimers_suppress_personal_economics(self):
        filing = {
            "cik": "0001853921",
            "accession_no": "0001193125-26-316503",
            "company": "Scribe Therapeutics, Inc.",
            "people": [
                {
                    "name": "Behzad Aghazadeh, Ph.D.",
                    "shares": 697_650,
                    "shares_after_ipo": 697_650,
                    "cash_value": 21_389_949.0,
                    "ipo_value": 10_464_750.0,
                    "locked_shares": 697_650,
                    "locked_value": 21_389_949.0,
                    "valuation_as_of": "2026-09-03",
                    "is_beneficial_owner": True,
                },
                {
                    "name": "Carl L. Gordon, Ph.D., CFA",
                    "shares": 348_825,
                    "shares_after_ipo": 348_825,
                    "cash_value": 10_694_974.5,
                    "ipo_value": 5_232_375.0,
                    "locked_shares": 348_825,
                    "locked_value": 10_694_974.5,
                    "valuation_as_of": "2026-09-03",
                    "is_beneficial_owner": True,
                },
            ],
        }

        normalized = suppress_unsupported_person_economics(filing)

        for person in normalized["people"]:
            self.assertTrue(person["is_beneficial_owner"])
            self.assertIsNotNone(person["shares"])
            self.assertIsNotNone(person["shares_after_ipo"])
            for field in (
                "cash_value",
                "ipo_value",
                "locked_shares",
                "locked_value",
                "valuation_as_of",
            ):
                self.assertIsNone(person[field], f"{person['name']} {field}")

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

import unittest

from person_economic_attribution_guard import suppress_unsupported_person_economics


class ElectraFinalPersonEconomicsTests(unittest.TestCase):
    def test_final_424b4_fund_positions_keep_sec_shares_but_suppress_personal_economics(self):
        filing = {
            "cik": "0002088082",
            "accession_no": "0001193125-26-395670",
            "company": "Electra Therapeutics, Inc.",
            "signals": ["Largest named holding currently valued at approximately $84M"],
            "people": [
                {
                    "name": "Carl L. Gordon, Ph.D., C.F.A.",
                    "shares": 5_551_837,
                    "shares_after_ipo": 5_551_837,
                    "cash_value": 73_561_840.25,
                    "ipo_value": 83_277_555.0,
                    "locked_shares": 5_551_837,
                    "locked_value": 73_561_840.25,
                    "valuation_as_of": "2026-09-19",
                    "is_beneficial_owner": True,
                },
                {
                    "name": "Beth Seidenberg, M.D.",
                    "shares": 6_347_539,
                    "shares_after_ipo": 6_347_539,
                    "cash_value": 84_104_891.75,
                    "ipo_value": 95_213_085.0,
                    "locked_shares": 6_347_539,
                    "locked_value": 84_104_891.75,
                    "valuation_as_of": "2026-09-19",
                    "is_beneficial_owner": True,
                },
            ],
        }

        normalized = suppress_unsupported_person_economics(filing)

        self.assertEqual(normalized["people"][0]["shares"], 5_551_837)
        self.assertEqual(normalized["people"][1]["shares"], 6_347_539)
        for person in normalized["people"]:
            self.assertTrue(person["is_beneficial_owner"])
            for field in (
                "cash_value",
                "ipo_value",
                "locked_shares",
                "locked_value",
                "valuation_as_of",
            ):
                self.assertIsNone(person[field], f"{person['name']} {field}")

        self.assertEqual(normalized["signals"], [])

    def test_final_accession_exception_remains_exact_count_constrained(self):
        filing = {
            "cik": "0002088082",
            "accession_no": "0001193125-26-395670",
            "people": [
                {
                    "name": "Carl L. Gordon, Ph.D., C.F.A.",
                    "shares": 5_551_838,
                    "cash_value": 73_561_853.50,
                    "ipo_value": 83_277_570.0,
                }
            ],
        }

        normalized = suppress_unsupported_person_economics(filing)
        self.assertEqual(normalized["people"][0]["cash_value"], 73_561_853.50)
        self.assertEqual(normalized["people"][0]["ipo_value"], 83_277_570.0)


if __name__ == "__main__":
    unittest.main()

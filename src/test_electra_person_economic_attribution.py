import unittest

from person_economic_attribution_guard import suppress_unsupported_person_economics


class ElectraPersonEconomicAttributionTests(unittest.TestCase):
    def test_fund_positions_keep_sec_share_counts_without_personal_economics(self):
        filing = {
            "cik": "0002088082",
            "accession_no": "0001193125-26-389755",
            "company": "Electra Therapeutics, Inc.",
            "signals": ["Largest named holding currently valued at approximately $120M"],
            "people": [
                {
                    "name": "Carl L. Gordon, Ph.D., C.F.A.",
                    "shares": 5_548_593,
                    "shares_after_ipo": 5_548_593,
                    "cash_value": 110_000_000.0,
                    "ipo_value": 83_228_895.0,
                    "locked_shares": 5_548_593,
                    "locked_value": 110_000_000.0,
                    "valuation_as_of": "2026-09-16",
                    "is_beneficial_owner": True,
                },
                {
                    "name": "Beth Seidenberg, M.D.",
                    "shares": 6_341_824,
                    "shares_after_ipo": 6_341_824,
                    "cash_value": 120_000_000.0,
                    "ipo_value": 95_127_360.0,
                    "locked_shares": 6_341_824,
                    "locked_value": 120_000_000.0,
                    "valuation_as_of": "2026-09-16",
                    "is_beneficial_owner": True,
                },
                {
                    "name": "Entities affiliated with OrbiMed",
                    "shares": 5_548_593,
                    "cash_value": 110_000_000.0,
                    "ipo_value": 83_228_895.0,
                },
                {
                    "name": "Entities affiliated with Westlake BioPartners Fund I, L.P.",
                    "shares": 6_341_824,
                    "cash_value": 120_000_000.0,
                    "ipo_value": 95_127_360.0,
                },
            ],
        }

        normalized = suppress_unsupported_person_economics(filing)

        for person in normalized["people"][:2]:
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

        self.assertEqual(normalized["people"][2]["cash_value"], 110_000_000.0)
        self.assertEqual(normalized["people"][3]["cash_value"], 120_000_000.0)
        self.assertEqual(
            normalized["signals"],
            ["Largest named holding currently valued at approximately $120M"],
        )

    def test_exact_counts_survive_accession_promotion_but_changed_counts_fail_closed(self):
        promoted = {
            "cik": "0002088082",
            "accession_no": "0001193125-26-999999",
            "people": [
                {
                    "name": "Carl L. Gordon, Ph.D., C.F.A.",
                    "shares": 5_548_593,
                    "cash_value": 100_000_000.0,
                },
                {
                    "name": "Beth Seidenberg, M.D.",
                    "shares": 6_341_824,
                    "cash_value": 110_000_000.0,
                },
            ],
        }
        changed = {
            "cik": "0002088082",
            "accession_no": "0001193125-26-999999",
            "people": [
                {
                    "name": "Carl L. Gordon, Ph.D., C.F.A.",
                    "shares": 5_548_594,
                    "cash_value": 100_000_000.0,
                }
            ],
        }

        normalized_promoted = suppress_unsupported_person_economics(promoted)
        normalized_changed = suppress_unsupported_person_economics(changed)

        self.assertIsNone(normalized_promoted["people"][0]["cash_value"])
        self.assertIsNone(normalized_promoted["people"][1]["cash_value"])
        self.assertEqual(normalized_changed["people"][0]["cash_value"], 100_000_000.0)


if __name__ == "__main__":
    unittest.main()

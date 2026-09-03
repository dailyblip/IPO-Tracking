import unittest

from person_economic_attribution_guard import suppress_unsupported_person_economics


class YeswayPersonEconomicAttributionTests(unittest.TestCase):
    def test_trkla_brookwood_aggregate_keeps_reported_shares_but_suppresses_personal_economics(self):
        filing = {
            "cik": "0001859836",
            "accession_no": "0001104659-26-047210",
            "company": "Yesway, Inc.",
            "signals": ["Largest named holding currently valued at approximately $1.1B"],
            "people": [
                {
                    "name": "Brookwood Financial Partners, LLC",
                    "shares": 45_875_727,
                    "cash_value": 1_104_687_506.16,
                    "ipo_value": 917_514_540.0,
                },
                {
                    "name": "Thomas N. Trkla",
                    "shares": 46_225_020,
                    "shares_after_ipo": 46_225_020,
                    "cash_value": 1_113_098_481.60,
                    "ipo_value": 924_500_400.0,
                    "liquid_shares": 1_000,
                    "liquid_value": 24_080.0,
                    "locked_shares": 46_224_020,
                    "locked_value": 1_113_074_401.60,
                    "cash_realized_ipo": 10_000_000.0,
                    "valuation_as_of": "2026-09-03",
                },
            ],
        }

        normalized = suppress_unsupported_person_economics(filing)
        brookwood, trkla = normalized["people"]

        # SEC reporting supports the aggregate beneficial-ownership quantity, but
        # the Brookwood-controlled indirect positions are not established as the
        # reporting person's full personal economic interest.
        self.assertEqual(trkla["shares"], 46_225_020)
        self.assertEqual(trkla["shares_after_ipo"], 46_225_020)
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
            self.assertIsNone(trkla[field], field)

        # The separate Brookwood entity record remains evidence-supported.
        self.assertEqual(brookwood["cash_value"], 1_104_687_506.16)
        self.assertEqual(brookwood["ipo_value"], 917_514_540.0)


if __name__ == "__main__":
    unittest.main()

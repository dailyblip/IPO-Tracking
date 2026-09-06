import unittest

import filing_price_history


class FilingPriceRangePrecedenceTests(unittest.TestCase):
    def priced_row(self, **overrides):
        row = {
            "id": "standard-nuclear-regression",
            "company": "Standard Nuclear, Inc.",
            "ticker": "STDN",
            "cik": "0002086716",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-07-16",
            "filing_date": "2026-06-23",
            "pricing_date": "2026-07-15",
            "offering_price": 15.0,
            "filing_price": None,
        }
        row.update(overrides)
        return row

    def history(self):
        return [
            {
                "form_type": "S-1/A",
                "accession_no": "fixed-pricing-amendment",
                "filing_date": "2026-07-15",
                "file_number": "333-300001",
            },
            {
                "form_type": "S-1/A",
                "accession_no": "marketed-range-amendment",
                "filing_date": "2026-07-07",
                "file_number": "333-300001",
            },
            {
                "form_type": "S-1",
                "accession_no": "initial",
                "filing_date": "2026-06-23",
                "file_number": "333-300001",
            },
        ]

    def registration_loader(self, cik, metadata):
        self.assertEqual(cik, "0002086716")
        accession = metadata["accession_no"]
        if accession == "fixed-pricing-amendment":
            return (
                {"price_range": {"range_low": 15.0, "range_high": 15.0}},
                "https://www.sec.gov/fixed-pricing-amendment",
            )
        if accession == "marketed-range-amendment":
            return (
                {"price_range": {"range_low": 18.0, "range_high": 21.0}},
                "https://www.sec.gov/marketed-range-amendment",
            )
        return (
            {"price_range": {"range_low": None, "range_high": None}},
            "https://www.sec.gov/initial",
        )

    def test_blank_priced_row_preserves_marketed_range_over_later_fixed_price(self):
        calls = []

        def loader(cik, metadata):
            calls.append(metadata["accession_no"])
            return self.registration_loader(cik, metadata)

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [self.priced_row()]},
            history_loader=lambda cik, pricing_date: self.history(),
            registration_loader=loader,
        )

        filing = payload["filings"][0]
        self.assertEqual(calls, ["fixed-pricing-amendment", "marketed-range-amendment"])
        self.assertEqual(filing["filing_price"], "18-21")
        self.assertEqual(filing["price_range"], "18-21")
        self.assertEqual(
            filing["filing_price_source"]["accession_no"],
            "marketed-range-amendment",
        )
        self.assertEqual((recovered, checked), (1, 1))

    def test_existing_fixed_price_source_is_rechecked_for_earlier_marketed_range(self):
        row = self.priced_row(
            filing_price="15",
            price_range="15",
            filing_price_source={
                "source": "SEC EDGAR",
                "form": "S-1/A",
                "filing_date": "2026-07-15",
                "accession_no": "fixed-pricing-amendment",
                "sec_url": "https://www.sec.gov/fixed-pricing-amendment",
            },
        )

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [row]},
            history_loader=lambda cik, pricing_date: self.history(),
            registration_loader=self.registration_loader,
        )

        filing = payload["filings"][0]
        self.assertEqual(filing["filing_price"], "18-21")
        self.assertEqual(filing["price_range"], "18-21")
        self.assertEqual(
            filing["filing_price_source"]["accession_no"],
            "marketed-range-amendment",
        )
        self.assertEqual((recovered, checked), (1, 1))


if __name__ == "__main__":
    unittest.main()

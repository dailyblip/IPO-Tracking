import unittest

import filing_price_history


class FilingPriceHistoryStaleSourceTests(unittest.TestCase):
    def test_verified_blank_removes_stale_source_metadata(self):
        calls = []
        row = {
            "id": "final-blank-source",
            "company": "Example Corp.",
            "ticker": "EXM",
            "cik": "1234567",
            "form": "424B4",
            "stage": "Priced",
            "filing_date": "2026-08-01",
            "pricing_date": "2026-08-20",
            "offering_price": 17.0,
            "filing_price": None,
            "price_range": None,
            "filing_price_source": {
                "source": "SEC EDGAR",
                "form": "S-1/A",
                "filing_date": "2026-08-18",
                "accession_no": "stale-amend",
                "sec_url": "https://www.sec.gov/stale-amend",
            },
        }
        history = [
            {
                "form_type": "S-1/A",
                "accession_no": "amend",
                "filing_date": "2026-08-18",
            },
            {
                "form_type": "S-1",
                "accession_no": "initial",
                "filing_date": "2026-08-01",
            },
        ]

        def registration_loader(cik, metadata):
            calls.append(metadata["accession_no"])
            return (
                {"price_range": {"range_low": None, "range_high": None}},
                f"https://www.sec.gov/{metadata['accession_no']}",
            )

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [row]},
            history_loader=lambda cik, pricing_date: history,
            registration_loader=registration_loader,
        )

        filing = payload["filings"][0]
        self.assertEqual(calls, ["amend", "initial"])
        self.assertIsNone(filing["filing_price"])
        self.assertIsNone(filing["price_range"])
        self.assertNotIn("filing_price_source", filing)
        self.assertEqual((recovered, checked), (0, 1))


if __name__ == "__main__":
    unittest.main()

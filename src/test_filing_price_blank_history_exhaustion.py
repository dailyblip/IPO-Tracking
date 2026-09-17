import unittest

import filing_price_history


class FilingPriceBlankHistoryExhaustionTests(unittest.TestCase):
    def test_blank_is_accepted_only_after_every_prepricing_registration_is_checked(self):
        filing = {
            "id": "final-blank-range",
            "company": "Example Systems Inc.",
            "ticker": "EXMP",
            "cik": "1234567",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-09-10",
            "pricing_date": "2026-09-10",
            "offering_price": 18.0,
            "filing_price": None,
        }
        history = [
            {
                "form_type": "S-1/A",
                "accession_no": "amend-latest",
                "filing_date": "2026-09-08",
            },
            {
                "form_type": "S-1/A",
                "accession_no": "amend-earlier",
                "filing_date": "2026-09-03",
            },
            {
                "form_type": "S-1",
                "accession_no": "initial",
                "filing_date": "2026-08-20",
            },
        ]
        inspected = []

        def registration_loader(cik, metadata):
            self.assertEqual(cik, "0001234567")
            inspected.append(metadata["accession_no"])
            return (
                {"price_range": {"range_low": None, "range_high": None}},
                f"https://www.sec.gov/{metadata['accession_no']}",
            )

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [filing]},
            history_loader=lambda cik, pricing_date: history,
            registration_loader=registration_loader,
        )

        published = payload["filings"][0]
        self.assertEqual(
            inspected,
            ["amend-latest", "amend-earlier", "initial"],
            "A priced blank Filing Price must exhaust relevant S-1/S-1A history before the blank is accepted.",
        )
        self.assertIsNone(published["filing_price"])
        self.assertNotIn("filing_price_source", published)
        self.assertEqual((recovered, checked), (0, 1))


if __name__ == "__main__":
    unittest.main()

import unittest

import filing_price_history


class FilingPricePartialHistoryFailClosedTests(unittest.TestCase):
    def _priced_row(self):
        return {
            "id": "priced-1",
            "company": "Example Corp.",
            "ticker": "EXM",
            "cik": "1234567",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-08-20",
            "filing_date": "2026-08-01",
            "pricing_date": "2026-08-20",
            "offering_price": 17.0,
            "filing_price": None,
        }

    def test_failed_newest_amendment_cannot_fall_back_to_older_range(self):
        history = [
            {
                "form_type": "S-1/A",
                "accession_no": "newest-amendment",
                "filing_date": "2026-08-18",
            },
            {
                "form_type": "S-1/A",
                "accession_no": "older-amendment",
                "filing_date": "2026-08-15",
            },
        ]
        calls = []

        def registration_loader(cik, metadata):
            calls.append(metadata["accession_no"])
            if metadata["accession_no"] == "newest-amendment":
                raise RuntimeError("SEC document unavailable")
            return (
                {"price_range": {"range_low": 14, "range_high": 16}},
                "https://www.sec.gov/older-amendment",
            )

        with self.assertRaises(filing_price_history.FilingPriceHistoryError):
            filing_price_history.recover_payload_filing_prices(
                {"filings": [self._priced_row()]},
                history_loader=lambda cik, pricing_date: history,
                registration_loader=registration_loader,
            )

        self.assertEqual(calls, ["newest-amendment"])

    def test_partial_history_failure_cannot_accept_blank_filing_price(self):
        history = [
            {
                "form_type": "S-1/A",
                "accession_no": "newest-amendment",
                "filing_date": "2026-08-18",
            },
            {
                "form_type": "S-1",
                "accession_no": "initial-filing",
                "filing_date": "2026-08-01",
            },
        ]
        calls = []

        def registration_loader(cik, metadata):
            calls.append(metadata["accession_no"])
            if metadata["accession_no"] == "newest-amendment":
                return (
                    {"price_range": {"range_low": None, "range_high": None}},
                    "https://www.sec.gov/newest-amendment",
                )
            raise RuntimeError("SEC document unavailable")

        with self.assertRaises(filing_price_history.FilingPriceHistoryError):
            filing_price_history.recover_payload_filing_prices(
                {"filings": [self._priced_row()]},
                history_loader=lambda cik, pricing_date: history,
                registration_loader=registration_loader,
            )

        self.assertEqual(calls, ["newest-amendment", "initial-filing"])


if __name__ == "__main__":
    unittest.main()

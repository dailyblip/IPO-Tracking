import unittest

import market_quote_release_gate


class MarketQuoteAcceptanceTimezoneTests(unittest.TestCase):
    ACCESSION = "0001234567-26-123456"

    def _filing(self):
        return {
            "id": self.ACCESSION,
            "accession_no": self.ACCESSION,
            "company": "Example Technology Holdings Inc.",
            "ticker": "EXMP",
            "cik": "0001234567",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-08-31",
            "pricing_date": "2026-08-31",
            "offering_price": 15.0,
            "current_price": 18.25,
            "price_updated": "2026-08-31T14:15:00+00:00",
        }

    def _sec_profile(self, acceptance):
        return {
            "cik": 1234567,
            "name": "Example Technology Holdings Inc.",
            "tickers": ["EXMP"],
            "filings": {
                "recent": {
                    "accessionNumber": [self.ACCESSION],
                    "form": ["424B4"],
                    "filingDate": ["2026-08-31"],
                    "acceptanceDateTime": [acceptance],
                }
            },
        }

    def test_offsetless_iso_acceptance_time_fails_closed(self):
        reason = market_quote_release_gate._same_day_quote_chronology_reason(
            self._filing(),
            self._sec_profile("2026-08-31T10:00:00"),
        )
        self.assertEqual(
            reason,
            "SEC submissions lacks a valid final 424B4 acceptance time",
        )

    def test_explicit_offset_acceptance_time_remains_authoritative(self):
        reason = market_quote_release_gate._same_day_quote_chronology_reason(
            self._filing(),
            self._sec_profile("2026-08-31T10:00:00-04:00"),
        )
        self.assertIsNone(reason)

    def test_compact_edgar_acceptance_time_remains_eastern(self):
        reason = market_quote_release_gate._same_day_quote_chronology_reason(
            self._filing(),
            self._sec_profile("20260831100000"),
        )
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()

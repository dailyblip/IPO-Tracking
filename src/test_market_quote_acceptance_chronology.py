import unittest

import market_quote_release_gate as gate


class MarketQuoteAcceptanceChronologyTests(unittest.TestCase):
    ACCESSION = "0001234567-26-123456"

    def _filing(self, price_updated):
        return {
            "company": "Example Priced Inc.",
            "ticker": "EXMP",
            "cik": "0001234567",
            "accession_no": self.ACCESSION,
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-08-31",
            "pricing_date": "2026-08-31",
            "offering_price": 15.0,
            "current_price": 18.25,
            "price_updated": price_updated,
        }

    def _sec_profile(self, acceptance="20260831100000"):
        return {
            "filings": {
                "recent": {
                    "accessionNumber": [self.ACCESSION],
                    "form": ["424B4"],
                    "filingDate": ["2026-08-31"],
                    "acceptanceDateTime": [acceptance],
                }
            }
        }

    def test_same_day_quote_strictly_after_sec_acceptance_is_allowed(self):
        filing = self._filing("2026-08-31T14:00:01+00:00")

        reason = gate._same_day_quote_chronology_reason(
            filing,
            self._sec_profile(),
        )

        self.assertIsNone(reason)

    def test_same_day_quote_equal_to_sec_acceptance_fails_closed(self):
        filing = self._filing("2026-08-31T14:00:00+00:00")

        reason = gate._same_day_quote_chronology_reason(
            filing,
            self._sec_profile(),
        )

        self.assertEqual(
            reason,
            "same-day quote does not postdate final 424B4 SEC acceptance",
        )

    def test_same_day_quote_before_sec_acceptance_fails_closed(self):
        filing = self._filing("2026-08-31T13:59:59+00:00")

        reason = gate._same_day_quote_chronology_reason(
            filing,
            self._sec_profile(),
        )

        self.assertEqual(
            reason,
            "same-day quote does not postdate final 424B4 SEC acceptance",
        )

    def test_utc_rollover_still_uses_sec_eastern_calendar(self):
        filing = self._filing("2026-09-01T00:30:00+00:00")
        # 00:30 UTC on September 1 is still August 31 in New York. A 21:00
        # Eastern SEC acceptance is therefore later than this quote.
        sec_profile = self._sec_profile("20260831210000")

        reason = gate._same_day_quote_chronology_reason(filing, sec_profile)

        self.assertEqual(
            reason,
            "same-day quote does not postdate final 424B4 SEC acceptance",
        )

    def test_duplicate_same_day_final_accession_fails_closed(self):
        filing = self._filing("2026-08-31T15:00:00+00:00")
        sec_profile = {
            "filings": {
                "recent": {
                    "accessionNumber": [self.ACCESSION, self.ACCESSION],
                    "form": ["424B4", "424B4"],
                    "filingDate": ["2026-08-31", "2026-08-31"],
                    "acceptanceDateTime": ["20260831100000", "20260831100100"],
                }
            }
        }

        reason = gate._same_day_quote_chronology_reason(filing, sec_profile)

        self.assertEqual(
            reason,
            "SEC submissions cannot uniquely confirm the same-day final 424B4",
        )

    def test_malformed_acceptance_time_fails_closed(self):
        filing = self._filing("2026-08-31T15:00:00+00:00")

        reason = gate._same_day_quote_chronology_reason(
            filing,
            self._sec_profile("not-a-timestamp"),
        )

        self.assertEqual(
            reason,
            "SEC submissions lacks a valid final 424B4 acceptance time",
        )

    def test_quote_on_later_eastern_day_does_not_require_intraday_sec_metadata(self):
        filing = self._filing("2026-09-01T04:00:00+00:00")

        reason = gate._same_day_quote_chronology_reason(filing, {})

        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()

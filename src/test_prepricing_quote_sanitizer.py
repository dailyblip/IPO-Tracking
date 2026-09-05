from datetime import datetime, timezone
import unittest
from unittest.mock import patch

import prepricing_quote_sanitizer
from prepricing_quote_sanitizer import sanitize_payload


class PrepricingQuoteSanitizerTests(unittest.TestCase):
    def test_removes_market_quotes_from_s1_record(self):
        payload = {
            "filings": [{
                "id": "s1:1",
                "form": "S-1/A",
                "stage": "Pre-pricing",
                "ticker": "LYNX",
                "current_price": 13.65,
                "price_updated": "2026-08-26T20:05:29+00:00",
                "people": [{
                    "name": "Example Owner",
                    "cash_value": 123,
                    "liquid_value": 45,
                    "locked_value": 78,
                    "valuation_as_of": "2026-08-26",
                }],
            }]
        }
        sanitized, changed = sanitize_payload(payload)
        filing = sanitized["filings"][0]
        self.assertEqual(changed, 1)
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertNotIn("cash_value", filing["people"][0])
        self.assertNotIn("valuation_as_of", filing["people"][0])

    def test_preserves_market_quote_for_complete_final_424b4(self):
        payload = {
            "filings": [{
                "id": "priced-1",
                "form": "424B4",
                "stage": "Priced",
                "filed": "2026-08-27",
                "pricing_date": "2026-08-26",
                "offering_price": 18.0,
                "current_price": 24.13,
                "price_updated": "2026-08-26T20:05:29+00:00",
                "people": [{"cash_value": 100}],
            }]
        }
        sanitized, changed = sanitize_payload(payload)
        filing = sanitized["filings"][0]
        self.assertEqual(changed, 0)
        self.assertEqual(filing["current_price"], 24.13)
        self.assertEqual(filing["people"][0]["cash_value"], 100)

    def test_removes_quote_when_pricing_date_is_after_final_424b4_filing(self):
        payload = {
            "filings": [{
                "id": "impossible-final-chronology",
                "form": "424B4",
                "stage": "Priced",
                "filed": "2026-08-26",
                "pricing_date": "2026-08-27",
                "offering_price": 18.0,
                "current_price": 24.13,
                "price_updated": "2026-08-27T20:05:29+00:00",
                "people": [{
                    "cash_value": 100,
                    "valuation_as_of": "2026-08-27",
                }],
            }]
        }
        sanitized, changed = sanitize_payload(payload)
        filing = sanitized["filings"][0]
        self.assertEqual(changed, 1)
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertNotIn("cash_value", filing["people"][0])
        self.assertNotIn("valuation_as_of", filing["people"][0])

    def test_removes_quote_when_quote_timestamp_predates_pricing(self):
        payload = {
            "filings": [{
                "id": "stale-prepricing-quote",
                "form": "424B4",
                "stage": "Priced",
                "filed": "2026-08-27",
                "pricing_date": "2026-08-26",
                "offering_price": 18.0,
                "current_price": 24.13,
                "price_updated": "2026-08-25T23:59:59+00:00",
                "people": [{
                    "cash_value": 100,
                    "valuation_as_of": "2026-08-25",
                }],
            }]
        }
        sanitized, changed = sanitize_payload(payload)
        filing = sanitized["filings"][0]
        self.assertEqual(changed, 1)
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertNotIn("cash_value", filing["people"][0])
        self.assertNotIn("valuation_as_of", filing["people"][0])

    def test_removes_quote_without_release_safe_quote_timestamp(self):
        for index, timestamp in enumerate((
            None,
            "",
            "not-a-timestamp",
            "2026-08-27T20:05:29",
            "2099-01-01T00:00:00+00:00",
        )):
            with self.subTest(timestamp=timestamp):
                filing = {
                    "id": f"invalid-quote-time-{index}",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-08-27",
                    "pricing_date": "2026-08-26",
                    "offering_price": 18.0,
                    "current_price": 24.13,
                    "people": [{
                        "cash_value": 100,
                        "valuation_as_of": "2026-08-27",
                    }],
                }
                if timestamp is not None:
                    filing["price_updated"] = timestamp
                payload = {"filings": [filing]}
                sanitized, changed = sanitize_payload(payload)
                result = sanitized["filings"][0]
                self.assertEqual(changed, 1)
                self.assertNotIn("current_price", result)
                self.assertNotIn("price_updated", result)
                self.assertNotIn("cash_value", result["people"][0])
                self.assertNotIn("valuation_as_of", result["people"][0])

    def test_removes_quote_with_future_clock_time_on_same_utc_date(self):
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                fixed = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
                return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)

        payload = {
            "filings": [{
                "id": "same-day-future-quote",
                "form": "424B4",
                "stage": "Priced",
                "filed": "2026-08-20",
                "pricing_date": "2026-08-19",
                "offering_price": 18.0,
                "current_price": 24.13,
                "price_updated": "2026-09-05T18:00:00+00:00",
                "people": [{
                    "name": "Holder",
                    "cash_value": 100.0,
                    "valuation_as_of": "2026-09-05",
                }],
            }]
        }

        with patch.object(prepricing_quote_sanitizer, "datetime", FixedDateTime):
            sanitized, changed = sanitize_payload(payload)

        filing = sanitized["filings"][0]
        person = filing["people"][0]
        self.assertEqual(changed, 1)
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertNotIn("cash_value", person)
        self.assertNotIn("valuation_as_of", person)

    def test_priced_record_without_current_quote_clears_stale_market_derivatives(self):
        payload = {
            "filings": [{
                "id": "whitehawk-regression",
                "form": "424B4",
                "stage": "Priced",
                "pricing_date": "2026-06-09",
                "offering_price": 26.0,
                "price_updated": "2026-08-29T19:56:40+00:00",
                "signals": [
                    "9 named beneficial owners disclosed",
                    "Largest named holding currently valued at approximately $86M",
                    "Lock-up terms captured for liquidity-event follow-up",
                ],
                "people": [{
                    "name": "Omega Capital Partners, LP",
                    "shares": 3_261_216,
                    "cash_value": 86_487_448.32,
                    "ipo_value": 84_791_616.0,
                    "cash_realized_ipo": 1_000_000.0,
                    "liquid_shares": 100_000,
                    "liquid_value": 2_652_000.0,
                    "locked_shares": 200_000,
                    "locked_value": 5_304_000.0,
                    "valuation_as_of": "2026-08-29",
                }],
            }]
        }
        sanitized, changed = sanitize_payload(payload)
        filing = sanitized["filings"][0]
        person = filing["people"][0]

        self.assertEqual(changed, 1)
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        for field in ("cash_value", "liquid_value", "locked_value", "valuation_as_of"):
            self.assertNotIn(field, person)
        self.assertEqual(person["shares"], 3_261_216)
        self.assertEqual(person["ipo_value"], 84_791_616.0)
        self.assertEqual(person["cash_realized_ipo"], 1_000_000.0)
        self.assertEqual(
            filing["signals"],
            [
                "9 named beneficial owners disclosed",
                "Lock-up terms captured for liquidity-event follow-up",
            ],
        )

    def test_removes_all_market_value_signal_wording_without_quote(self):
        payload = {
            "filings": [{
                "id": "stale-signal-wording",
                "form": "424B4",
                "stage": "Priced",
                "pricing_date": "2026-08-26",
                "offering_price": 18.0,
                "signals": [
                    "Founder current market value is approximately $5M",
                    "Sponsor currently valued at approximately $7M",
                    "Offering priced at $18.00 per share",
                ],
            }]
        }
        sanitized, changed = sanitize_payload(payload)
        filing = sanitized["filings"][0]
        self.assertEqual(changed, 1)
        self.assertEqual(
            filing["signals"],
            ["Offering priced at $18.00 per share"],
        )

    def test_removes_quote_from_424b4_with_prepricing_stage(self):
        payload = {
            "filings": [{
                "id": "malformed-stage",
                "form": "424B4",
                "stage": "Pre-pricing",
                "pricing_date": "2026-08-26",
                "offering_price": 18.0,
                "current_price": 24.13,
                "price_updated": "2026-08-26T20:05:29+00:00",
                "people": [{"cash_value": 100, "valuation_as_of": "2026-08-26"}],
            }]
        }
        sanitized, changed = sanitize_payload(payload)
        filing = sanitized["filings"][0]
        self.assertEqual(changed, 1)
        self.assertNotIn("current_price", filing)
        self.assertNotIn("price_updated", filing)
        self.assertNotIn("cash_value", filing["people"][0])
        self.assertNotIn("valuation_as_of", filing["people"][0])

    def test_removes_quote_from_incomplete_priced_424b4(self):
        cases = (
            {"pricing_date": None, "offering_price": 18.0},
            {"pricing_date": "2026-08-26", "offering_price": None},
            {"pricing_date": "not-a-date", "offering_price": 18.0},
            {"pricing_date": "2026-08-26", "offering_price": 0},
        )
        for index, fields in enumerate(cases):
            with self.subTest(fields=fields):
                payload = {
                    "filings": [{
                        "id": f"incomplete-{index}",
                        "form": "424B4",
                        "stage": "Priced",
                        "current_price": 24.13,
                        "price_updated": "2026-08-26T20:05:29+00:00",
                        "people": [{"cash_value": 100}],
                        **fields,
                    }]
                }
                sanitized, changed = sanitize_payload(payload)
                filing = sanitized["filings"][0]
                self.assertEqual(changed, 1)
                self.assertNotIn("current_price", filing)
                self.assertNotIn("cash_value", filing["people"][0])


if __name__ == "__main__":
    unittest.main()

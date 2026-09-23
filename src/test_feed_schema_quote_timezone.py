import unittest

from feed_schema_contract import _lifecycle_semantic_errors


class FeedSchemaQuoteTimezoneTests(unittest.TestCase):
    def _priced_filing(self, price_updated):
        return {
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-08-27",
            "filing_date": "2026-08-01",
            "pricing_date": "2026-08-27",
            "offering_price": 18.0,
            "current_price": 19.5,
            "price_updated": price_updated,
        }

    def test_utc_rollover_quote_on_prior_sec_day_is_release_blocking(self):
        failures = _lifecycle_semantic_errors(
            0,
            self._priced_filing("2026-08-27T00:30:00+00:00"),
            generated_at="2026-08-27T00:45:00+00:00",
        )

        self.assertTrue(
            any("cannot predate Pricing Date" in failure for failure in failures),
            failures,
        )
        self.assertTrue(
            any("cannot predate the final 424B4 filing date" in failure for failure in failures),
            failures,
        )

    def test_quote_on_same_sec_eastern_day_remains_calendar_valid(self):
        failures = _lifecycle_semantic_errors(
            0,
            self._priced_filing("2026-08-27T14:00:00+00:00"),
            generated_at="2026-08-27T14:15:00+00:00",
        )

        self.assertFalse(
            any("cannot predate" in failure for failure in failures),
            failures,
        )


if __name__ == "__main__":
    unittest.main()

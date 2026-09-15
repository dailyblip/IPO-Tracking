from __future__ import annotations

import unittest

from dashboard_export import SCHEMA_VERSION
from feed_schema_contract import validate_payload


class FeedSchemaQuoteTimestampContractTests(unittest.TestCase):
    def _filing(self, **overrides):
        filing = {
            "id": "test-quote-1",
            "company": "Example Corp.",
            "ticker": "EXM",
            "cik": "0001234567",
            "accession_no": "0001193125-26-123456",
            "form": "424B4",
            "filed": "2026-08-20",
            "filing_date": "2026-08-01",
            "pricing_date": "2026-08-20",
            "stage": "Priced",
            "priority": "Medium",
            "status": "New",
            "value": 150000000,
            "value_label": "$150M",
            "offering_price": 17.0,
            "current_price": 19.25,
            "price_updated": "2026-08-21T15:30:00+00:00",
            "people_count": 0,
            "signals": [],
            "people": [],
            "sec_url": "https://www.sec.gov/example",
        }
        filing.update(overrides)
        return filing

    def _payload(self, filing, generated_at="2026-08-21T16:00:00+00:00"):
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "source": "SEC EDGAR",
            "filings": [filing],
        }

    def test_valid_priced_quote_timestamp_is_allowed(self):
        self.assertEqual([], validate_payload(self._payload(self._filing())))

    def test_current_price_requires_provider_timestamp(self):
        failures = validate_payload(self._payload(self._filing(price_updated=None)))
        self.assertTrue(
            any("requires a timezone-aware provider timestamp" in failure for failure in failures),
            failures,
        )

    def test_current_price_rejects_naive_provider_timestamp(self):
        failures = validate_payload(
            self._payload(self._filing(price_updated="2026-08-21T15:30:00"))
        )
        self.assertTrue(
            any("requires a timezone-aware provider timestamp" in failure for failure in failures),
            failures,
        )

    def test_current_price_timestamp_cannot_predate_pricing(self):
        failures = validate_payload(
            self._payload(self._filing(price_updated="2026-08-19T23:59:59+00:00"))
        )
        self.assertTrue(
            any("cannot predate Pricing Date" in failure for failure in failures),
            failures,
        )

    def test_current_price_timestamp_cannot_predate_final_filing(self):
        failures = validate_payload(
            self._payload(
                self._filing(
                    pricing_date="2026-08-19",
                    filed="2026-08-20",
                    price_updated="2026-08-19T23:59:59+00:00",
                )
            )
        )
        self.assertTrue(
            any("cannot predate the final 424B4 filing date" in failure for failure in failures),
            failures,
        )

    def test_current_price_timestamp_cannot_be_future(self):
        failures = validate_payload(
            self._payload(self._filing(price_updated="2999-01-01T00:00:00+00:00"))
        )
        self.assertTrue(
            any("provider timestamp cannot be in the future" in failure for failure in failures),
            failures,
        )

    def test_current_price_timestamp_cannot_be_stale_at_feed_generation(self):
        failures = validate_payload(
            self._payload(
                self._filing(price_updated="2026-08-21T15:30:00+00:00"),
                generated_at="2026-08-29T15:30:01+00:00",
            )
        )
        self.assertTrue(
            any("too old for the feed generation time" in failure for failure in failures),
            failures,
        )

    def test_current_price_timestamp_cannot_exceed_provider_future_skew_at_generation(self):
        failures = validate_payload(
            self._payload(
                self._filing(price_updated="2026-08-21T15:06:00+00:00"),
                generated_at="2026-08-21T15:00:00+00:00",
            )
        )
        self.assertTrue(
            any("too far after the feed generation time" in failure for failure in failures),
            failures,
        )

    def test_provider_clock_skew_within_release_window_is_allowed(self):
        payload = self._payload(
            self._filing(price_updated="2026-08-21T15:04:00+00:00"),
            generated_at="2026-08-21T15:00:00+00:00",
        )
        self.assertEqual([], validate_payload(payload))

    def test_orphan_provider_timestamp_is_release_blocking(self):
        failures = validate_payload(
            self._payload(self._filing(current_price=None, price_updated="2026-08-21T15:30:00+00:00"))
        )
        self.assertTrue(
            any("cannot remain populated without Current Price" in failure for failure in failures),
            failures,
        )


if __name__ == "__main__":
    unittest.main()

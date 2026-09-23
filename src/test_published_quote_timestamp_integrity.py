import json
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"
EASTERN = ZoneInfo("America/New_York")


def _number(value):
    if value in (None, "", "—"):
        return None
    try:
        return float(str(value).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None


def _iso_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def _aware_datetime(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _eastern_date(value):
    parsed = _aware_datetime(value)
    return parsed.astimezone(EASTERN).date() if parsed is not None else None


class PublishedQuoteTimestampIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        cls.filings = payload.get("filings", []) if isinstance(payload, dict) else payload

    def test_quote_calendar_day_is_eastern_not_utc(self):
        self.assertEqual(
            _eastern_date("2026-09-18T00:30:00Z"),
            date(2026, 9, 17),
        )

    def test_published_quotes_have_canonical_post_pricing_nonfuture_timestamps(self):
        """A published Current Price must be a real quote after IPO pricing and final filing.

        This validates the exact generated feed, not only the quote sanitizer unit
        behavior. Secondary quote data may legitimately be absent when identity or
        freshness cannot be verified, so rows without Current Price are ignored.
        SEC filing/pricing chronology uses the Eastern calendar because a quote just
        after midnight UTC can still belong to the prior U.S. market day.
        """
        failures = []
        now = datetime.now(timezone.utc)

        for filing in self.filings:
            if _number(filing.get("current_price")) is None:
                continue

            label = filing.get("company") or filing.get("id") or "unknown filing"
            pricing_date = _iso_date(filing.get("pricing_date"))
            final_filing_date = _iso_date(filing.get("filed"))
            quote_time = _aware_datetime(filing.get("price_updated"))

            if pricing_date is None:
                failures.append(f"{label}: Current Price exists without canonical Pricing Date")
                continue
            if final_filing_date is None:
                failures.append(
                    f"{label}: Current Price exists without canonical final 424B4 Filed date"
                )
                continue
            if quote_time is None:
                failures.append(
                    f"{label}: Current Price exists without a timezone-aware price_updated timestamp"
                )
                continue

            quote_utc = quote_time.astimezone(timezone.utc)
            quote_eastern_date = quote_time.astimezone(EASTERN).date()
            if quote_utc > now:
                failures.append(
                    f"{label}: price_updated {quote_utc.isoformat()} is in the future"
                )
            if quote_eastern_date < pricing_date:
                failures.append(
                    f"{label}: Eastern quote date {quote_eastern_date.isoformat()} predates Pricing Date "
                    f"{pricing_date.isoformat()}"
                )
            if quote_eastern_date < final_filing_date:
                failures.append(
                    f"{label}: Eastern quote date {quote_eastern_date.isoformat()} predates final 424B4 Filed "
                    f"{final_filing_date.isoformat()}"
                )

        self.assertEqual(
            failures,
            [],
            "Published quote timestamp failures: " + "; ".join(failures[:10]),
        )


if __name__ == "__main__":
    unittest.main()

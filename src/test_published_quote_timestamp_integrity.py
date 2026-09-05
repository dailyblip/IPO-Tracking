import json
import unittest
from datetime import date, datetime, timezone
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"


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


class PublishedQuoteTimestampIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        cls.filings = payload.get("filings", []) if isinstance(payload, dict) else payload

    def test_published_quotes_have_canonical_post_pricing_nonfuture_timestamps(self):
        """A published Current Price must be tied to a real post-IPO quote timestamp.

        This validates the exact generated feed, not only the quote sanitizer unit
        behavior. Secondary quote data may legitimately be absent when identity or
        freshness cannot be verified, so rows without Current Price are ignored.
        """
        failures = []
        now = datetime.now(timezone.utc)

        for filing in self.filings:
            if _number(filing.get("current_price")) is None:
                continue

            label = filing.get("company") or filing.get("id") or "unknown filing"
            pricing_date = _iso_date(filing.get("pricing_date"))
            quote_time = _aware_datetime(filing.get("price_updated"))

            if pricing_date is None:
                failures.append(f"{label}: Current Price exists without canonical Pricing Date")
                continue
            if quote_time is None:
                failures.append(
                    f"{label}: Current Price exists without a timezone-aware price_updated timestamp"
                )
                continue

            quote_utc = quote_time.astimezone(timezone.utc)
            if quote_utc > now:
                failures.append(
                    f"{label}: price_updated {quote_utc.isoformat()} is in the future"
                )
            if quote_utc.date() < pricing_date:
                failures.append(
                    f"{label}: price_updated {quote_utc.date().isoformat()} predates Pricing Date "
                    f"{pricing_date.isoformat()}"
                )

        self.assertEqual(
            failures,
            [],
            "Published quote timestamp failures: " + "; ".join(failures[:10]),
        )


if __name__ == "__main__":
    unittest.main()

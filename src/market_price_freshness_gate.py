"""Clear Current Price values whose provider timestamp is not release-fresh.

Current Price is secondary market data. ``price_lookup`` validates every newly
retrieved quote against the market provider's timestamp and ``dashboard_export``
now preserves that authoritative provider timestamp in ``price_updated``. The feed's
``generated_at`` value records pipeline retrieval time, so those two timestamps are
not expected to be identical.

Run this gate immediately after ``main.py``. A populated quote survives only when it
has a positive price and a timezone-aware provider timestamp that is no older than
the same freshness window enforced by ``price_lookup``, is not materially in the
future relative to the pipeline retrieval time, and does not predate the authoritative
Pricing Date. Invalid/stale/pre-pricing quotes and all public market-value derivatives
are cleared before lifecycle reconciliation continues.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

import dashboard_export
from price_lookup import MAX_FUTURE_SKEW_SECONDS, MAX_QUOTE_AGE_SECONDS

_MARKET_VALUE_SIGNAL_MARKERS = ("currently valued", "current market value")


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _timestamp(value):
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


def _date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def _strip_quote_derived_fields(filing: dict) -> None:
    """Remove a stale quote plus every public value derived from that quote."""
    filing.pop("current_price", None)
    filing.pop("price_updated", None)

    for person in filing.get("people") or []:
        if not isinstance(person, dict):
            continue
        for field in ("cash_value", "liquid_value", "locked_value", "valuation_as_of"):
            person.pop(field, None)

    signals = filing.get("signals")
    if isinstance(signals, list):
        filing["signals"] = [
            signal
            for signal in signals
            if not any(
                marker in str(signal or "").casefold()
                for marker in _MARKET_VALUE_SIGNAL_MARKERS
            )
        ]


def sanitize_payload(payload: dict) -> tuple[dict, list[dict]]:
    """Clear populated quotes that are stale, invalid, or predate IPO pricing."""
    if not isinstance(payload, dict):
        raise ValueError("Market-price freshness gate requires an object payload")

    refresh_marker = str(payload.get("generated_at") or "").strip()
    refresh_time = _timestamp(refresh_marker)
    stale = []
    for filing in payload.get("filings") or []:
        if not isinstance(filing, dict) or filing.get("current_price") in (None, ""):
            continue

        price = _number(filing.get("current_price"))
        price_updated = str(filing.get("price_updated") or "").strip()
        quote_time = _timestamp(price_updated)
        pricing_date_raw = str(filing.get("pricing_date") or "").strip()
        pricing_date = _date(pricing_date_raw)
        quote_date = (
            quote_time.astimezone(timezone.utc).date()
            if quote_time is not None
            else None
        )
        age_seconds = (
            (refresh_time - quote_time).total_seconds()
            if refresh_time is not None and quote_time is not None
            else None
        )
        if (
            price is not None
            and price > 0
            and age_seconds is not None
            and -MAX_FUTURE_SKEW_SECONDS <= age_seconds <= MAX_QUOTE_AGE_SECONDS
            and pricing_date is not None
            and quote_date is not None
            and quote_date >= pricing_date
        ):
            continue

        stale.append(
            {
                "company": filing.get("company") or filing.get("id") or "<unknown>",
                "ticker": filing.get("ticker") or "",
                "price_updated": price_updated or None,
                "pricing_date": pricing_date_raw or None,
                "generated_at": refresh_marker or None,
            }
        )
        _strip_quote_derived_fields(filing)

    return payload, stale


def sanitize_file(path: Path) -> list[dict]:
    """Apply the freshness gate atomically and keep the companion CSV synchronized."""
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload, stale = sanitize_payload(payload)
    if stale:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    dashboard_export.write_dashboard_csv(payload.get("filings", []), path)
    return stale


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Clear Current Price values with invalid, stale, or pre-pricing "
            "provider timestamps."
        )
    )
    parser.add_argument("feed", help="Path to docs/data/filings.json")
    args = parser.parse_args(argv)

    stale = sanitize_file(Path(args.feed))
    if stale:
        labels = ", ".join(
            f"{item['company']} ({item['ticker'] or 'no ticker'})" for item in stale
        )
        print(
            f"Market-price freshness gate cleared {len(stale)} invalid/stale "
            f"quote(s): {labels}"
        )
    else:
        print(
            "Market-price freshness gate: all populated Current Price values are "
            "provider-fresh and post-pricing"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Clear Current Price values that were not refreshed in the current pipeline run.

The quote fetcher deliberately returns ``None`` for a ticker when Finnhub returns a
stale/invalid quote or a ticker-specific lookup fails. ``dashboard_export`` preserves
an existing Current Price when that happens so partial refresh callers do not erase
unrelated data. For the full daily/backfill pipelines, however, every published
trading ticker is attempted. A quote that still carries an older ``price_updated``
after that full refresh is therefore unverified stale state and must not survive.

Run this gate immediately after ``main.py``. At that point a successfully refreshed
quote has the exact same timestamp as the feed's ``generated_at`` value because
``refresh_market_prices`` writes both from the same ``updated_at`` value. Later
pipeline steps are free to change ``generated_at`` after this gate has completed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import dashboard_export

_MARKET_VALUE_SIGNAL_MARKERS = ("currently valued", "current market value")


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


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
    """Clear populated quotes not proven fresh in this exact pipeline refresh."""
    if not isinstance(payload, dict):
        raise ValueError("Market-price freshness gate requires an object payload")

    refresh_marker = str(payload.get("generated_at") or "").strip()
    stale = []
    for filing in payload.get("filings") or []:
        if not isinstance(filing, dict) or filing.get("current_price") in (None, ""):
            continue

        price = _number(filing.get("current_price"))
        price_updated = str(filing.get("price_updated") or "").strip()
        if price is not None and price > 0 and refresh_marker and price_updated == refresh_marker:
            continue

        stale.append(
            {
                "company": filing.get("company") or filing.get("id") or "<unknown>",
                "ticker": filing.get("ticker") or "",
                "price_updated": price_updated or None,
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
        description="Clear Current Price values that were not refreshed in this pipeline run."
    )
    parser.add_argument("feed", help="Path to docs/data/filings.json")
    args = parser.parse_args(argv)

    stale = sanitize_file(Path(args.feed))
    if stale:
        labels = ", ".join(
            f"{item['company']} ({item['ticker'] or 'no ticker'})" for item in stale
        )
        print(f"Market-price freshness gate cleared {len(stale)} stale quote(s): {labels}")
    else:
        print("Market-price freshness gate: all populated Current Price values were refreshed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

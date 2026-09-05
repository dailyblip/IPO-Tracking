"""Remove market-price fields from IPO records that are not safely quoteable.

Ticker symbols can collide with already-trading securities before an IPO begins
trading. Publishing those provider quotes on an S-1/S-1A record is therefore a
data-integrity defect. Current Price is allowed only when a final 424B4 row also
has a priced lifecycle state, an authoritative pricing date, a positive final
IPO price, and a positive current quote. A malformed/incomplete lifecycle or a
priced row without a publishable quote must fail closed and lose market-derived
holder values rather than retaining stale quote arithmetic.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path


_MARKET_VALUE_SIGNAL_MARKERS = ("currently valued", "current market value")
_MARKET_DERIVED_PERSON_FIELDS = (
    "cash_value",
    "liquid_value",
    "locked_value",
    "valuation_as_of",
)


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _canonical_nonfuture_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.isoformat() != raw or parsed > date.today():
        return None
    return parsed


def is_priced_ipo(filing: dict) -> bool:
    """Return True only for a release-safe final priced lifecycle state."""
    if str(filing.get("form") or "").strip().upper() != "424B4":
        return False
    if str(filing.get("stage") or "").strip().casefold() != "priced":
        return False
    pricing_date = _canonical_nonfuture_date(filing.get("pricing_date"))
    if pricing_date is None:
        return False

    # ``filed`` is the SEC filing date of the current public row. ``filing_date``
    # is the original S-1 date and must not be used for this comparison. A final
    # 424B4 without a canonical SEC filing date is not release-safe, and a pricing
    # date after that filing date is impossible. In either case the row must not
    # retain a live quote even if an earlier sanitizer was bypassed or ordering
    # changes later.
    filed_date = _canonical_nonfuture_date(filing.get("filed"))
    if filed_date is None or pricing_date > filed_date:
        return False

    final_price = _number(filing.get("offering_price"))
    return final_price is not None and final_price > 0


def has_release_safe_market_quote(filing: dict) -> bool:
    """Require both a safely priced lifecycle and a positive published quote."""
    if not is_priced_ipo(filing):
        return False
    current_price = _number(filing.get("current_price"))
    return current_price is not None and current_price > 0


def sanitize_payload(payload: dict) -> tuple[dict, int]:
    changed = 0
    for filing in payload.get("filings", []):
        if not isinstance(filing, dict) or has_release_safe_market_quote(filing):
            continue
        touched = False
        for field in ("current_price", "price_updated"):
            if field in filing:
                filing.pop(field, None)
                touched = True

        # Without a release-safe filing-level quote, holder-level current market
        # values have no publishable basis. Preserve SEC-supported ownership facts,
        # IPO-value arithmetic, and realized IPO cash; clear only quote derivatives.
        for person in filing.get("people", []):
            if not isinstance(person, dict):
                continue
            for field in _MARKET_DERIVED_PERSON_FIELDS:
                if field in person:
                    person.pop(field, None)
                    touched = True

        # A stale public signal can imply that a current quote still exists even
        # after the quote itself is absent. Remove every known market-value wording,
        # not only the legacy "Largest named holding" sentence.
        signals = filing.get("signals")
        if isinstance(signals, list):
            filtered_signals = [
                signal
                for signal in signals
                if not (
                    isinstance(signal, str)
                    and any(
                        marker in signal.casefold()
                        for marker in _MARKET_VALUE_SIGNAL_MARKERS
                    )
                )
            ]
            if len(filtered_signals) != len(signals):
                filing["signals"] = filtered_signals
                touched = True

        if touched:
            changed += 1
    return payload, changed


def sanitize_file(path: str | Path) -> int:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload, changed = sanitize_payload(payload)
    if changed:
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp.replace(path)
        try:
            from dashboard_export import write_dashboard_csv
            write_dashboard_csv(payload.get("filings", []), path)
        except ImportError:
            pass
    return changed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Remove unsafe lifecycle or unsupported market-derived quote fields")
    parser.add_argument("path", nargs="?", default="../docs/data/filings.json")
    args = parser.parse_args()
    count = sanitize_file(args.path)
    print(f"Sanitized {count} filing(s) with unsafe market-derived fields")

"""Remove market-price fields from IPO records that are not yet safely priced/trading.

Ticker symbols can collide with already-trading securities before an IPO begins
trading. Publishing those provider quotes on an S-1/S-1A record is therefore a
data-integrity defect. Current Price is allowed only when a final 424B4 row also
has a priced lifecycle state, an authoritative pricing date, and a positive final
IPO price. A malformed or incomplete 424B4 must fail closed and lose market-derived
fields rather than being treated as trading solely because of its form type.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path


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
    if _canonical_nonfuture_date(filing.get("pricing_date")) is None:
        return False
    final_price = _number(filing.get("offering_price"))
    return final_price is not None and final_price > 0


def sanitize_payload(payload: dict) -> tuple[dict, int]:
    changed = 0
    for filing in payload.get("filings", []):
        if not isinstance(filing, dict) or is_priced_ipo(filing):
            continue
        touched = False
        for field in ("current_price", "price_updated"):
            if field in filing:
                filing.pop(field, None)
                touched = True
        # Records that are not release-safe priced IPOs must not carry market-value
        # calculations derived from a ticker quote either. Preserve filing-supported
        # ownership facts and clear only quote-derived values.
        for person in filing.get("people", []):
            if not isinstance(person, dict):
                continue
            for field in ("cash_value", "liquid_value", "locked_value", "valuation_as_of"):
                if field in person:
                    person.pop(field, None)
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

    parser = argparse.ArgumentParser(description="Remove invalid pre-pricing or unsafe lifecycle market quotes")
    parser.add_argument("path", nargs="?", default="../docs/data/filings.json")
    args = parser.parse_args()
    count = sanitize_file(args.path)
    print(f"Sanitized {count} filing(s) with unsafe market-derived fields")

"""Remove market-price fields from IPO records that are not yet priced/trading.

Ticker symbols can collide with already-trading securities before an IPO begins
trading. Publishing those provider quotes on an S-1/S-1A record is therefore a
data-integrity defect. Current Price is allowed only for final 424B4 IPO rows.
"""

from __future__ import annotations

import json
from pathlib import Path


def is_priced_ipo(filing: dict) -> bool:
    return str(filing.get("form") or "").strip().upper() == "424B4"


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
        # Pre-pricing records should not carry market-value calculations derived
        # from a ticker quote either. Preserve only filing-supported facts.
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

    parser = argparse.ArgumentParser(description="Remove invalid pre-pricing market quotes")
    parser.add_argument("path", nargs="?", default="../docs/data/filings.json")
    args = parser.parse_args()
    count = sanitize_file(args.path)
    print(f"Sanitized {count} pre-pricing filing(s) with market-derived fields")

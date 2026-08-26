"""Remove impossible lifecycle dates from the public Research Monitor feed.

Never infer a replacement date. If a stored initial S-1 filing date occurs after
an already-priced IPO's pricing date, clear the bad initial filing date and keep
the authoritative pricing/424B4 facts intact. CSV output is regenerated so the
public exports remain synchronized.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from dashboard_export import write_dashboard_csv

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"


def _iso_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def sanitize_payload(payload: dict) -> tuple[dict, int]:
    filings = payload.get("filings", []) if isinstance(payload, dict) else []
    changed = 0
    for filing in filings:
        if not isinstance(filing, dict):
            continue
        pricing_date = _iso_date(filing.get("pricing_date"))
        filing_date = _iso_date(filing.get("filing_date"))
        if pricing_date and filing_date and filing_date > pricing_date:
            filing["filing_date"] = None
            changed += 1
    return payload, changed


def sanitize_file(path: Path = DEFAULT_PATH) -> int:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload, changed = sanitize_payload(payload)
    if not changed:
        return 0

    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)
    write_dashboard_csv(payload.get("filings", []), path)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Sanitize impossible IPO lifecycle dates")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    changed = sanitize_file(args.path)
    print(f"Sanitized {changed} impossible lifecycle date(s).")


if __name__ == "__main__":
    main()

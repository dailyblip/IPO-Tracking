"""Remove impossible lifecycle dates from the public Research Monitor feed.

Never infer a replacement date. The stored ``filing_date`` is the lifecycle's
initial S-1 date, so it cannot occur after either the SEC filing date of the
current public row or an already-priced IPO's pricing date. Likewise, a final
424B4 Pricing Date cannot occur after that final prospectus was filed. Clear only
an impossible date and keep the remaining authoritative lifecycle facts intact;
the final-pricing release gate will fail closed if a priced row is left without a
valid Pricing Date. CSV output is regenerated so the public exports remain
synchronized.
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
        filed_date = _iso_date(filing.get("filed"))
        pricing_date = _iso_date(filing.get("pricing_date"))
        filing_date = _iso_date(filing.get("filing_date"))
        form = str(filing.get("form") or "").strip().upper()
        stage = str(filing.get("stage") or "").strip().casefold()

        # A company cannot price after the final 424B4 that reports that pricing.
        # Do not move the date to a plausible value: clear the conflict so the
        # final-pricing release gate can omit the row until authoritative recovery.
        if (
            form == "424B4"
            and stage == "priced"
            and filed_date is not None
            and pricing_date is not None
            and pricing_date > filed_date
        ):
            filing["pricing_date"] = None
            pricing_date = None
            changed += 1

        if filing_date is None:
            continue
        if (
            (filed_date and filing_date > filed_date)
            or (pricing_date and filing_date > pricing_date)
        ):
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

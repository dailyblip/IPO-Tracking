"""Fail closed on unresolved final 424B4 pricing states.

Lifecycle reconciliation and pricing-date recovery get the first opportunity to
repair final prospectus records. After those passes, a 424B4 is release-grade only
when it is explicitly Priced, has canonical non-future final filing and Pricing
Dates in possible chronology, and carries a positive authoritative Final IPO
Price. Offering size and preliminary Filing Price are deliberately not required
here: qualifying IPOs may have unknown size, and preliminary price history is
repaired by the separate S-1/S-1A history pass.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

import dashboard_export

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"


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


def is_release_grade_final(filing: dict) -> bool:
    """Return True for non-final rows or a fully resolved final 424B4 state."""
    if str((filing or {}).get("form") or "").strip().upper() != "424B4":
        return True
    if str(filing.get("stage") or "").strip().casefold() != "priced":
        return False

    pricing_date = _canonical_nonfuture_date(filing.get("pricing_date"))
    filed_date = _canonical_nonfuture_date(filing.get("filed"))
    if pricing_date is None or filed_date is None:
        return False
    if pricing_date > filed_date:
        return False

    final_price = _number(filing.get("offering_price"))
    return final_price is not None and final_price > 0


def sanitize_payload(payload: dict):
    """Remove final prospectus rows whose authoritative pricing state is unresolved."""
    filings = payload.get("filings") if isinstance(payload, dict) else None
    if not isinstance(filings, list):
        raise ValueError("Public feed must contain a filings list")

    kept = []
    removed = []
    for filing in filings:
        if not isinstance(filing, dict) or is_release_grade_final(filing):
            kept.append(filing)
            continue
        removed.append(filing)

    if not removed:
        return payload, removed

    updated = dict(payload)
    updated["filings"] = kept
    updated["generated_at"] = datetime.now(timezone.utc).isoformat()
    return updated, removed


def sanitize_file(path: str | Path = DEFAULT_PATH):
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload, removed = sanitize_payload(payload)
    if removed:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    dashboard_export.write_dashboard_csv(payload.get("filings", []), path)
    return removed


def main() -> None:
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    removed = sanitize_file(target)
    if removed:
        labels = ", ".join(
            str(item.get("company") or item.get("id") or "<unknown>") for item in removed
        )
        print(f"Removed {len(removed)} unresolved final-pricing record(s): {labels}")
    else:
        print("No unresolved final-pricing records found.")


if __name__ == "__main__":
    main()

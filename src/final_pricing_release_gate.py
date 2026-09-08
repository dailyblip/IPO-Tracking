"""Fail closed on unresolved final 424B4 pricing states.

Lifecycle reconciliation and pricing-date recovery get the first opportunity to
repair final prospectus records. After those passes, a 424B4 is release-grade only
when it is explicitly Priced, has canonical non-future final filing and Pricing
Dates in possible chronology, carries a positive authoritative Final IPO Price,
and its SEC Archives URL matches the published issuer CIK and accession number.
Offering size and preliminary Filing Price are deliberately not required here:
qualifying IPOs may have unknown size, and preliminary price history is repaired
by the separate S-1/S-1A history pass.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path

import dashboard_export

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"
ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SEC_ARCHIVES_FILING_PATTERN = re.compile(
    r"^https://www\.sec\.gov/Archives/edgar/data/(\d+)/(\d{18})/"
    r"(\d{10}-\d{2}-\d{6})-index\.htm$",
    re.IGNORECASE,
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


def _canonical_cik(value):
    if value is None or isinstance(value, bool):
        return None
    raw = str(value).strip()
    if not raw or not raw.isdigit():
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _has_matching_sec_identity(filing):
    """Require the final-price row to resolve to its own canonical SEC filing URL."""
    accession = filing.get("accession_no")
    if not isinstance(accession, str):
        return False
    accession = accession.strip()
    if not ACCESSION_PATTERN.fullmatch(accession):
        return False

    cik = _canonical_cik(filing.get("cik"))
    if cik is None:
        return False

    sec_url = filing.get("sec_url")
    if not isinstance(sec_url, str):
        return False
    sec_url = sec_url.strip()
    match = SEC_ARCHIVES_FILING_PATTERN.fullmatch(sec_url)
    if not match:
        return False

    archive_cik, archive_accession, index_accession = match.groups()
    if int(archive_cik) != cik:
        return False

    accession_compact = accession.replace("-", "")
    return archive_accession == accession_compact and index_accession == accession


def is_release_grade_final(filing: dict) -> bool:
    """Return True for non-final rows or a fully resolved final 424B4 state."""
    if not isinstance(filing, dict):
        return False
    if str(filing.get("form") or "").strip().upper() != "424B4":
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
    if final_price is None or final_price <= 0:
        return False
    return _has_matching_sec_identity(filing)


def sanitize_payload(payload: dict):
    """Remove malformed entries and final prospectus rows with unresolved pricing."""
    filings = payload.get("filings") if isinstance(payload, dict) else None
    if not isinstance(filings, list):
        raise ValueError("Public feed must contain a filings list")

    kept = []
    removed = []
    for filing in filings:
        if is_release_grade_final(filing):
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
            str(item.get("company") or item.get("id") or "<unknown>")
            if isinstance(item, dict)
            else "<malformed entry>"
            for item in removed
        )
        print(f"Removed {len(removed)} unresolved final-pricing record(s): {labels}")
    else:
        print("No unresolved final-pricing records found.")


if __name__ == "__main__":
    main()

"""Remove follow-on/resale 424B4 records from the public IPO feed.

Research Monitor tracks company IPOs, not later registered offerings by companies
that are already SEC reporting issuers. A prior Exchange Act reporting form
before the candidate 424B4 is authoritative evidence that the company had already
entered the SEC reporting system before this offering. This includes domestic
current/periodic reports and foreign-private-issuer reports, including amendments.

This pass is deliberately conservative and date-aware: reports filed after or on
the same day as the candidate do not disqualify a historical IPO. SEC lookup
failure blocks the sanitizer instead of silently publishing an unverified candidate.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import dashboard_export
import edgar_client

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"
REPORTING_FORMS = {
    "8-K", "8-K/A", "10-Q", "10-Q/A", "10-K", "10-K/A",
    "6-K", "6-K/A", "20-F", "20-F/A", "40-F", "40-F/A",
}


def _iso_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def has_prior_periodic_report(submissions: dict, candidate_date: str) -> bool:
    """Return True when an authoritative SEC reporting form predates the offering."""
    cutoff = _iso_date(candidate_date)
    if cutoff is None:
        raise ValueError(f"Invalid candidate date: {candidate_date!r}")

    recent = (submissions or {}).get("filings", {}).get("recent", {})
    forms = recent.get("form", []) or []
    dates = recent.get("filingDate", []) or []
    for form, filing_date in zip(forms, dates):
        report_date = _iso_date(filing_date)
        if str(form or "").upper() in REPORTING_FORMS and report_date and report_date < cutoff:
            return True
    return False


def _load_submissions(cik: str) -> dict:
    padded_cik = str(cik or "").zfill(10)
    if not padded_cik.strip("0"):
        raise ValueError("Missing CIK for final 424B4 record")
    url = edgar_client.EDGAR_SUBMISSIONS_URL.format(cik=padded_cik)
    return edgar_client._request_json(url, edgar_client._get_headers())


def sanitize_payload(payload: dict, submissions_loader=_load_submissions):
    """Remove final offerings proven to post-date prior SEC reporting history."""
    filings = payload.get("filings", []) if isinstance(payload, dict) else []
    kept = []
    removed = []
    cache = {}

    for filing in filings:
        if not isinstance(filing, dict) or str(filing.get("form") or "").upper() != "424B4":
            kept.append(filing)
            continue

        cik = str(filing.get("cik") or "").strip()
        candidate_date = str(filing.get("pricing_date") or filing.get("filed") or "").strip()
        if not cik or _iso_date(candidate_date) is None:
            # Other release gates own missing identity/date errors; do not infer here.
            kept.append(filing)
            continue

        if cik not in cache:
            cache[cik] = submissions_loader(cik)
        if has_prior_periodic_report(cache[cik], candidate_date):
            removed.append(filing)
            continue
        kept.append(filing)

    if removed:
        updated = dict(payload)
        updated["filings"] = kept
        updated["generated_at"] = datetime.now(timezone.utc).isoformat()
        return updated, removed
    return payload, []


def sanitize_file(path: Path = DEFAULT_PATH) -> list:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload, removed = sanitize_payload(payload)
    if removed:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(path)
    dashboard_export.write_dashboard_csv(payload.get("filings", []), path)
    return removed


def main() -> None:
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    removed = sanitize_file(target)
    if removed:
        labels = ", ".join(str(item.get("company") or item.get("id") or "<unknown>") for item in removed)
        print(f"Removed {len(removed)} post-reporting follow-on/resale offering(s): {labels}")
    else:
        print("No post-reporting follow-on/resale offerings found.")


if __name__ == "__main__":
    main()

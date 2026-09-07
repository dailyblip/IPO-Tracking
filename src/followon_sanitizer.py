"""Remove follow-on/resale 424B4 records from the public IPO feed.

Research Monitor tracks company IPOs, not later registered offerings by companies
that are already SEC reporting issuers. A prior Exchange Act reporting form
before the candidate 424B4 is authoritative evidence that the company had already
entered the SEC reporting system before this offering. A prior Form S-3 or F-3,
including automatic-shelf and Rule 462(b) additional-registration variants, is
also affirmative reporting-history evidence because those short forms require
Exchange Act reporting eligibility. A prior Form 424B4 is separately dispositive
that the issuer already completed an earlier public offering prospectus and the
later 424B4 cannot be its first IPO.

This pass is deliberately conservative and date-aware. Same-day filings are
ordered only when SEC submissions supplies acceptance timestamps for both the
candidate and the possible prior reporting filing, and the comparison date is the
candidate's SEC filing date; otherwise same-day order is left unresolved. SEC
lookup failure or malformed core chronology metadata blocks the sanitizer instead
of silently publishing an unverified candidate.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import dashboard_export
import edgar_client

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"
REPORTING_FORMS = {
    "8-K", "8-K/A",
    "8-K12B", "8-K12B/A",
    "8-K12G3", "8-K12G3/A",
    "8-K15D5", "8-K15D5/A",
    "10-12B", "10-12B/A", "10-12G", "10-12G/A",
    "10-Q", "10-Q/A", "10-QT", "10-QT/A",
    "10-K", "10-K/A", "10-KT", "10-KT/A",
    "6-K", "6-K/A", "20-F", "20-F/A", "40-F", "40-F/A",
    "S-3", "S-3/A", "S-3ASR", "S-3ASR/A", "S-3MEF",
    "F-3", "F-3/A", "F-3ASR", "F-3ASR/A", "F-3MEF",
    "424B4",
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


def _iso_datetime(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _normalized_accession(value):
    return re.sub(r"\D", "", str(value or ""))


def _validated_recent_chronology(recent: dict):
    if not isinstance(recent, dict):
        raise RuntimeError("SEC submissions recent filing metadata is malformed")
    forms = recent.get("form")
    dates = recent.get("filingDate")
    if not isinstance(forms, list) or not isinstance(dates, list):
        raise RuntimeError("SEC submissions chronology arrays are missing or malformed")
    if len(forms) != len(dates):
        raise RuntimeError("SEC submissions chronology arrays are misaligned")

    normalized_forms = []
    normalized_dates = []
    for form, filing_date in zip(forms, dates):
        if not isinstance(form, str) or not form.strip():
            raise RuntimeError(
                f"SEC submissions chronology has invalid form metadata: {form!r}"
            )
        report_date = _iso_date(filing_date)
        if report_date is None:
            raise RuntimeError(
                f"SEC submissions chronology has invalid filingDate: {filing_date!r}"
            )
        normalized_forms.append(form.strip())
        normalized_dates.append(report_date.isoformat())
    return normalized_forms, normalized_dates


def _candidate_acceptance_time(
    recent: dict,
    candidate_accession: str,
    candidate_date: str,
):
    candidate_key = _normalized_accession(candidate_accession)
    cutoff = _iso_date(candidate_date)
    if not candidate_key or cutoff is None:
        return None
    accessions = recent.get("accessionNumber", []) or []
    filing_dates = recent.get("filingDate", []) or []
    acceptance_times = recent.get("acceptanceDateTime", []) or []
    for index, accession in enumerate(accessions):
        if _normalized_accession(accession) != candidate_key:
            continue
        if index >= len(filing_dates) or _iso_date(filing_dates[index]) != cutoff:
            return None
        if index >= len(acceptance_times):
            return None
        return _iso_datetime(acceptance_times[index])
    return None


def has_prior_periodic_report(
    submissions: dict,
    candidate_date: str,
    candidate_accession: str | None = None,
) -> bool:
    """Return True when authoritative SEC reporting/public-offering evidence predates the offering."""
    cutoff = _iso_date(candidate_date)
    if cutoff is None:
        raise ValueError(f"Invalid candidate date: {candidate_date!r}")

    recent = (submissions or {}).get("filings", {}).get("recent", {})
    forms, dates = _validated_recent_chronology(recent)
    acceptance_times = recent.get("acceptanceDateTime", []) or []
    candidate_accepted = _candidate_acceptance_time(
        recent,
        candidate_accession,
        candidate_date,
    )

    for index, (form, filing_date) in enumerate(zip(forms, dates)):
        report_date = _iso_date(filing_date)
        if str(form or "").upper() not in REPORTING_FORMS or report_date is None:
            continue
        if report_date < cutoff:
            return True
        if report_date != cutoff or candidate_accepted is None:
            continue
        if index >= len(acceptance_times):
            continue
        report_accepted = _iso_datetime(acceptance_times[index])
        if report_accepted is not None and report_accepted < candidate_accepted:
            return True
    return False


def _load_submissions(cik: str) -> dict:
    padded_cik = str(cik or "").zfill(10)
    if not padded_cik.strip("0"):
        raise ValueError("Missing CIK for final 424B4 record")
    url = edgar_client.EDGAR_SUBMISSIONS_URL.format(cik=padded_cik)
    return edgar_client._request_json(url, edgar_client._get_headers())


def sanitize_payload(payload: dict, submissions_loader=_load_submissions):
    """Remove final offerings proven to post-date prior SEC reporting/public-offering history."""
    filings = payload.get("filings", []) if isinstance(payload, dict) else []
    kept = []
    removed = []
    cache = {}

    for filing in filings:
        if not isinstance(filing, dict) or str(filing.get("form") or "").upper() != "424B4":
            kept.append(filing)
            continue

        cik = str(filing.get("cik") or "").strip()
        candidate_date = str(filing.get("filed") or filing.get("pricing_date") or "").strip()
        if not cik or _iso_date(candidate_date) is None:
            # Other release gates own missing identity/date errors; do not infer here.
            kept.append(filing)
            continue

        if cik not in cache:
            cache[cik] = submissions_loader(cik)
        if has_prior_periodic_report(
            cache[cik],
            candidate_date,
            candidate_accession=str(filing.get("accession_no") or "").strip(),
        ):
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

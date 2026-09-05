"""Release gate for SEC reporting history that has aged out of filings.recent.

SEC's submissions JSON keeps at least one year or 1,000 recent filings inline and
lists older history in additional JSON files under ``filings.files``. The normal
S-1 and 424B4 reporting-history gates inspect the inline block. This additive gate
checks those SEC-listed historical files before an issuer can remain published as
a first-time operating-company IPO.

A prior Exchange Act reporting form or registration statement, or a prior S-3/F-3
short-form registration that itself requires Exchange Act reporting eligibility,
must be filed strictly before the candidate. A prior 424B4 is separately
conclusive that the issuer already completed an earlier public offering prospectus.
Same-day evidence does not establish event order. Archive lookup failures block
final 424B4 publication; for pre-pricing S-1/S-1A rows they do not invent an
exclusion, matching the existing pre-pricing gate's conservative failure behavior.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from dashboard_export import write_dashboard_csv
import edgar_client

FORM_TYPES = {"S-1", "S-1/A"}
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
SUBMISSIONS_BASE_URL = "https://data.sec.gov/submissions"


class ArchivedReportingHistoryError(RuntimeError):
    """Raised when required historical SEC reporting evidence cannot be checked."""


def _iso_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def _columnar_history(payload):
    """Return the form/date column block from current or archived submissions JSON."""
    if not isinstance(payload, dict):
        return {}
    recent = payload.get("filings", {}).get("recent")
    if isinstance(recent, dict):
        return recent
    return payload


def _block_has_prior_reporting(payload, cutoff):
    block = _columnar_history(payload)
    forms = block.get("form", []) or []
    dates = block.get("filingDate", []) or []
    for form, filing_date in zip(forms, dates):
        report_date = _iso_date(filing_date)
        if str(form or "").strip().upper() in REPORTING_FORMS and report_date and report_date < cutoff:
            return True
    return False


def _archive_descriptors(submissions, cutoff):
    files = (submissions or {}).get("filings", {}).get("files", []) or []
    for descriptor in files:
        if not isinstance(descriptor, dict):
            continue
        name = str(descriptor.get("name") or "").strip()
        if not name:
            continue
        filing_from = _iso_date(descriptor.get("filingFrom"))
        # A historical block whose earliest filing is on/after the candidate
        # cannot contain a strictly earlier reporting form.
        if filing_from is not None and filing_from >= cutoff:
            continue
        yield descriptor


def _load_archive(name):
    name = str(name or "").strip()
    if not name or name != Path(name).name or not name.lower().endswith(".json"):
        raise ArchivedReportingHistoryError(
            f"SEC submissions history returned an invalid archive filename: {name!r}"
        )
    return edgar_client._request_json(
        f"{SUBMISSIONS_BASE_URL}/{name}",
        edgar_client._get_headers(),
    )


def has_prior_reporting_history(submissions, candidate_date, archive_loader=_load_archive):
    """Check current plus SEC-listed history for prior reporting/public-offering evidence."""
    cutoff = _iso_date(candidate_date)
    if cutoff is None:
        raise ValueError(f"Invalid candidate date: {candidate_date!r}")

    if _block_has_prior_reporting(submissions, cutoff):
        return True

    for descriptor in _archive_descriptors(submissions, cutoff):
        name = str(descriptor.get("name") or "").strip()
        archived = archive_loader(name)
        if _block_has_prior_reporting(archived, cutoff):
            return True
    return False


def _load_submissions(cik):
    padded_cik = str(cik or "").zfill(10)
    if not padded_cik.strip("0"):
        raise ArchivedReportingHistoryError("Missing CIK for SEC reporting-history review")
    return edgar_client._request_json(
        edgar_client.EDGAR_SUBMISSIONS_URL.format(cik=padded_cik),
        edgar_client._get_headers(),
    )


def _candidate_kind(record):
    if not isinstance(record, dict):
        return None
    form = str(record.get("form") or "").strip().upper()
    stage = str(record.get("stage") or "").strip().casefold()
    if form in FORM_TYPES and stage == "pre-pricing":
        return "prepricing"
    if form == "424B4":
        return "final"
    return None


def _candidate_date(record, kind):
    if kind == "prepricing":
        return str(record.get("filed") or record.get("filing_date") or "").strip()
    return str(record.get("pricing_date") or record.get("filed") or "").strip()


def _record_identity(record, kind):
    cik = str(record.get("cik") or "").zfill(10)
    accession = str(record.get("accession_no") or record.get("id") or "").strip().replace("-", "")
    candidate_date = _candidate_date(record, kind)
    return cik, accession or f"{record.get('form')}:{candidate_date}"


def sanitize_payloads(
    watch_payload,
    queue_payload,
    submissions_loader=_load_submissions,
    archive_loader=_load_archive,
):
    """Remove rows whose older SEC submissions prove the issuer already reported/offered."""
    cache = {}
    archive_cache = {}
    excluded_prepricing_ciks = set()
    excluded_final_ids = set()
    reviewed = set()

    def cached_archive_loader(name):
        if name not in archive_cache:
            archive_cache[name] = archive_loader(name)
        return archive_cache[name]

    all_rows = []
    for payload in (watch_payload, queue_payload):
        rows = payload.get("filings", []) if isinstance(payload, dict) else []
        if isinstance(rows, list):
            all_rows.extend(rows)

    for record in all_rows:
        kind = _candidate_kind(record)
        if kind is None:
            continue
        identity = _record_identity(record, kind)
        if identity in reviewed:
            continue
        reviewed.add(identity)

        cik = identity[0]
        candidate_date = _candidate_date(record, kind)
        if not cik.strip("0") or _iso_date(candidate_date) is None:
            continue

        try:
            if cik not in cache:
                cache[cik] = submissions_loader(cik)
            is_prior_reporting = has_prior_reporting_history(
                cache[cik], candidate_date, archive_loader=cached_archive_loader
            )
        except Exception as error:
            if kind == "prepricing":
                print(
                    f"[archived_reporting_history_gate] Historical SEC lookup failed for "
                    f"{record.get('company') or cik}; leaving pre-pricing row unclassified: {error}"
                )
                continue
            raise ArchivedReportingHistoryError(
                f"Could not complete historical SEC reporting review for "
                f"{record.get('company') or cik}: {error}"
            ) from error

        if not is_prior_reporting:
            continue
        if kind == "prepricing":
            excluded_prepricing_ciks.add(cik)
        else:
            excluded_final_ids.add(identity)

    def filter_rows(payload):
        rows = payload.get("filings", []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            return payload
        kept = []
        changed = False
        for record in rows:
            kind = _candidate_kind(record)
            remove = False
            if kind == "prepricing":
                cik = str(record.get("cik") or "").zfill(10)
                remove = cik in excluded_prepricing_ciks
            elif kind == "final":
                remove = _record_identity(record, kind) in excluded_final_ids
            if remove:
                changed = True
                continue
            kept.append(record)
        if not changed:
            return payload
        updated = dict(payload)
        updated["filings"] = kept
        updated["generated_at"] = datetime.now(timezone.utc).isoformat()
        return updated

    return (
        filter_rows(watch_payload),
        filter_rows(queue_payload),
        excluded_prepricing_ciks,
        excluded_final_ids,
    )


def _load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_payload(path, payload):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def apply_gate(watch_path, queue_path):
    watch_path = Path(watch_path)
    queue_path = Path(queue_path)
    watch = _load_payload(watch_path)
    queue = _load_payload(queue_path)
    updated_watch, updated_queue, excluded_s1, excluded_final = sanitize_payloads(watch, queue)

    if updated_watch != watch:
        _write_payload(watch_path, updated_watch)
    if updated_queue != queue:
        _write_payload(queue_path, updated_queue)
        write_dashboard_csv(updated_queue.get("filings", []), queue_path)

    print(
        f"[archived_reporting_history_gate] Removed {len(excluded_s1)} pre-pricing issuer(s) "
        f"and {len(excluded_final)} final follow-on offering(s) from archived SEC history"
    )
    return excluded_s1, excluded_final


def main():
    parser = argparse.ArgumentParser(
        description="Exclude IPO candidates with prior reporting/public-offering forms in archived SEC submissions history"
    )
    parser.add_argument("s1_watch")
    parser.add_argument("queue")
    args = parser.parse_args()
    apply_gate(Path(args.s1_watch), Path(args.queue))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

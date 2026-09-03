"""Release gate for pre-pricing S-1 registrations that are not first-time IPOs.

A current amendment can change formatting or cover wording enough to evade the
point-in-time resale classifier. SEC submissions metadata links amendments to the
same registration statement through ``fileNumber``. This gate checks earlier
S-1/S-1A filings in that exact registration lineage and excludes the current
pre-pricing row only when an earlier filing is deterministically resale/direct-
listing and the current record has no high-confidence issuer-primary offering
shares.

The gate also excludes an S-1/S-1A when SEC filing history proves the issuer was
already a reporting company before the candidate registration. This catches
post-SPAC/de-SPAC and other already-public issuers that can file a new S-1 before
they have a 10-K, including issuers whose prior Exchange Act reporting used
transition or foreign-private-issuer forms. Only reporting forms filed strictly
before the candidate S-1/S-1A are used.

Candidate coverage is the union of the S-1 watch payload and the public queue.
That prevents a regenerated or otherwise queue-only pre-pricing row from bypassing
the release gate merely because it is absent from ``s1_watch.json``.

Network/parser failures never create an exclusion. Different registration file
numbers are never inherited.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dashboard_export import write_dashboard_csv
import edgar_client
import filing_parser

FORM_TYPES = {"S-1", "S-1/A"}
REPORTING_FORMS = {
    "8-K", "8-K/A",
    "8-K12B", "8-K12B/A",
    "8-K12G3", "8-K12G3/A",
    "8-K15D5", "8-K15D5/A",
    "10-Q", "10-Q/A", "10-QT", "10-QT/A",
    "10-K", "10-K/A", "10-KT", "10-KT/A",
    "6-K", "6-K/A", "20-F", "20-F/A", "40-F", "40-F/A",
}


def _normalized_accession(value: str) -> str:
    return str(value or "").strip().replace("-", "")


def _has_authoritative_primary_evidence(record: dict) -> bool:
    try:
        shares = int(record.get("primary_offering_shares") or 0)
    except (TypeError, ValueError):
        shares = 0
    source = str(record.get("offering_size_source") or "").strip().casefold()
    confidence = str(record.get("offering_size_confidence") or "").strip().casefold()
    return shares > 0 and confidence == "high" and "primary offering" in source


def _recent_submission_rows(cik: str) -> list[dict]:
    """Return aligned recent SEC filing metadata for one issuer."""
    padded_cik = str(cik or "").zfill(10)
    if not padded_cik.strip("0"):
        return []

    url = edgar_client.EDGAR_SUBMISSIONS_URL.format(cik=padded_cik)
    data = edgar_client._request_json(url, edgar_client._get_headers())
    recent = data.get("filings", {}).get("recent", {}) or {}

    accessions = recent.get("accessionNumber", []) or []
    forms = recent.get("form", []) or []
    file_numbers = recent.get("fileNumber", []) or []
    filing_dates = recent.get("filingDate", []) or []
    primary_documents = recent.get("primaryDocument", []) or []
    count = min(
        len(accessions), len(forms), len(file_numbers),
        len(filing_dates), len(primary_documents)
    )

    return [
        {
            "accession_no": str(accessions[i] or "").strip(),
            "form": str(forms[i] or "").strip().upper(),
            "file_number": str(file_numbers[i] or "").strip(),
            "filing_date": str(filing_dates[i] or "").strip(),
            "primary_document": str(primary_documents[i] or "").strip(),
        }
        for i in range(count)
    ]


def already_reporting_before_registration(record: dict) -> bool:
    """Return True when SEC history proves the issuer reported before this S-1.

    A prior 8-K (including successor/assumption variants), 10-Q, 10-K, 10-QT,
    10-KT, 6-K, 20-F, or 40-F (including amendments) is affirmative evidence
    that the issuer was already subject to Exchange Act reporting. Requiring a
    strictly earlier filing date avoids inferring event order from same-day
    accessions.
    """
    if str(record.get("form") or "").strip().upper() not in FORM_TYPES:
        return False
    if str(record.get("stage") or "").strip().casefold() != "pre-pricing":
        return False

    cik = str(record.get("cik") or "").strip()
    current_date = str(record.get("filed") or record.get("filing_date") or "").strip()
    if not cik or not current_date:
        return False

    try:
        rows = _recent_submission_rows(cik)
    except Exception as error:
        print(
            f"[s1_registration_history_gate] SEC reporting-history lookup failed for "
            f"{record.get('company') or cik}: {error}"
        )
        return False

    return any(
        row.get("form") in REPORTING_FORMS
        and row.get("filing_date")
        and row["filing_date"] < current_date
        for row in rows
    )


def _same_registration_predecessors(cik: str, accession_no: str) -> list[dict]:
    """Return earlier S-1/S-1A filings sharing the current SEC file number."""
    rows = _recent_submission_rows(cik)
    if not rows or not accession_no:
        return []

    current_key = _normalized_accession(accession_no)
    current = next(
        (row for row in rows if _normalized_accession(row.get("accession_no")) == current_key),
        None,
    )
    if current is None:
        return []

    current_file_number = str(current.get("file_number") or "").strip()
    current_date = str(current.get("filing_date") or "").strip()
    if not current_file_number:
        return []

    predecessors = []
    for row in rows:
        accession = str(row.get("accession_no") or "").strip()
        form = str(row.get("form") or "").strip().upper()
        file_number = str(row.get("file_number") or "").strip()
        filing_date = str(row.get("filing_date") or "").strip()
        primary_document = str(row.get("primary_document") or "").strip()
        if not accession or _normalized_accession(accession) == current_key:
            continue
        if form not in FORM_TYPES or file_number != current_file_number:
            continue
        if current_date and filing_date and filing_date > current_date:
            continue
        if not primary_document:
            continue
        predecessors.append({
            "accession_no": accession,
            "form": form,
            "file_number": file_number,
            "filing_date": filing_date,
            "primary_document": primary_document,
        })

    return sorted(
        predecessors,
        key=lambda row: (row.get("filing_date", ""), row.get("accession_no", "")),
        reverse=True,
    )


def _primary_document_url(cik: str, filing: dict) -> str:
    folder = _normalized_accession(filing.get("accession_no"))
    document = str(filing.get("primary_document") or "").lstrip("/")
    return f"{edgar_client.EDGAR_ARCHIVES_BASE}/{int(cik)}/{folder}/{document}"


def amendment_inherits_resale_exclusion(record: dict) -> bool:
    """Return True only for authoritative same-registration resale history."""
    if str(record.get("form") or "").strip().upper() != "S-1/A":
        return False
    if str(record.get("stage") or "").strip().casefold() != "pre-pricing":
        return False
    if _has_authoritative_primary_evidence(record):
        return False

    cik = str(record.get("cik") or "").strip()
    accession_no = str(record.get("accession_no") or record.get("id") or "").strip()
    if not cik or not accession_no:
        return False

    try:
        predecessors = _same_registration_predecessors(cik, accession_no)
    except Exception as error:
        print(
            f"[s1_registration_history_gate] SEC history lookup failed for "
            f"{record.get('company') or accession_no}: {error}"
        )
        return False

    for predecessor in predecessors:
        try:
            soup = filing_parser.fetch_document(_primary_document_url(cik, predecessor))
            prior_text = soup.get_text(" ", strip=True)
        except Exception as error:
            print(
                f"[s1_registration_history_gate] Prior filing fetch failed for "
                f"{record.get('company') or accession_no}: {error}"
            )
            continue
        if edgar_client.check_direct_listing_indicators(prior_text):
            return True
    return False


def _load_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_payload(path: Path, payload: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def _is_prepricing_s1(record: dict) -> bool:
    return (
        isinstance(record, dict)
        and str(record.get("stage") or "").strip().casefold() == "pre-pricing"
        and str(record.get("form") or "").strip().upper() in FORM_TYPES
    )


def _candidate_identity(record: dict) -> tuple[str, str]:
    cik = str(record.get("cik") or "").zfill(10)
    accession = _normalized_accession(record.get("accession_no"))
    if accession:
        return cik, accession
    form = str(record.get("form") or "").strip().upper()
    filed = str(record.get("filed") or record.get("filing_date") or "").strip()
    return cik, f"{form}:{filed}"


def _candidate_records(*payloads: dict) -> list[dict]:
    """Return unique pre-pricing S-1/S-1A rows across all supplied payloads."""
    candidates = []
    seen = set()
    for payload in payloads:
        filings = payload.get("filings", []) if isinstance(payload, dict) else []
        if not isinstance(filings, list):
            continue
        for record in filings:
            if not _is_prepricing_s1(record):
                continue
            identity = _candidate_identity(record)
            if identity in seen:
                continue
            seen.add(identity)
            candidates.append(record)
    return candidates


def apply_gate(s1_watch_path: Path, queue_path: Path) -> set[str]:
    """Remove confirmed already-public or resale-lineage rows from pre-pricing outputs."""
    s1_watch_path = Path(s1_watch_path)
    queue_path = Path(queue_path)
    watch_payload = _load_payload(s1_watch_path)
    queue_payload = _load_payload(queue_path)

    excluded_ciks = set()
    for record in _candidate_records(watch_payload, queue_payload):
        already_reporting = already_reporting_before_registration(record)
        resale_history = False if already_reporting else amendment_inherits_resale_exclusion(record)
        if already_reporting or resale_history:
            cik = str(record.get("cik") or "").zfill(10)
            if cik.strip("0"):
                excluded_ciks.add(cik)
                if already_reporting:
                    reason = "SEC reporting forms predate the candidate S-1/S-1A"
                else:
                    reason = "prior filing in the same SEC registration statement is resale/direct-listing only"
                print(
                    f"[s1_registration_history_gate] Excluding "
                    f"{record.get('company') or cik}: {reason}"
                )

    if not excluded_ciks:
        print("[s1_registration_history_gate] No reporting-history or resale exclusions found")
        return set()

    watch_payload["filings"] = [
        row for row in watch_payload.get("filings", [])
        if str(row.get("cik") or "").zfill(10) not in excluded_ciks
    ]
    queue_payload["filings"] = [
        row for row in queue_payload.get("filings", [])
        if not (
            str(row.get("cik") or "").zfill(10) in excluded_ciks
            and str(row.get("stage") or "").strip().casefold() == "pre-pricing"
            and str(row.get("form") or "").strip().upper() in FORM_TYPES
        )
    ]

    _write_payload(s1_watch_path, watch_payload)
    _write_payload(queue_path, queue_payload)
    write_dashboard_csv(queue_payload.get("filings", []), queue_path)
    return excluded_ciks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exclude pre-pricing rows with prior reporting or authoritative resale history"
    )
    parser.add_argument("s1_watch")
    parser.add_argument("queue")
    args = parser.parse_args()
    excluded = apply_gate(Path(args.s1_watch), Path(args.queue))
    print(f"[s1_registration_history_gate] Removed {len(excluded)} issuer(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

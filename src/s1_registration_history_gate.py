"""Release gate for pre-pricing S-1 registrations that are not first-time IPOs.

A current amendment can change formatting or cover wording enough to evade the
point-in-time resale classifier. SEC submissions metadata links amendments to the
same registration statement through ``fileNumber``. This gate checks earlier
S-1/S-1A filings in that exact registration lineage and excludes the current
pre-pricing row only when an earlier filing is deterministically resale/direct-
listing and the current record has no high-confidence issuer-primary offering
shares.

The gate also excludes current S-1/S-1A registrations that SEC filing text
explicitly identifies as non-transferable subscription-rights offerings. Rights
offerings are capital-raising registrations, not initial public offerings, even
when a newly formed successor issuer uses Form S-1 in connection with a business
combination.

The gate also excludes a current S-1/S-1A when the prospectus itself explicitly
confirms that the issuer's common stock already trades in a public OTC market and
reports a pre-offering market price. An exchange uplisting or underwritten offering
by an already publicly traded issuer is not an initial public offering.

The gate also excludes an S-1/S-1A when SEC filing history proves the issuer was
already a reporting company before the candidate registration. This catches
post-SPAC/de-SPAC and other already-public issuers that can file a new S-1 before
they have a 10-K, including issuers whose prior Exchange Act reporting used
transition, foreign-private-issuer, or S-3/F-3 short-form registrations. Reporting
history must be provably earlier than the candidate S-1/S-1A: filing date orders
different days, while same-day rows require strict SEC acceptance-time ordering.

Candidate coverage is the union of the S-1 watch payload and the public queue.
That prevents a regenerated or otherwise queue-only pre-pricing row from bypassing
the release gate merely because it is absent from ``s1_watch.json``.

Network/parser failures never create an exclusion. Different registration file
numbers are never inherited.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dashboard_export import write_dashboard_csv
import edgar_client
import filing_parser

FORM_TYPES = {"S-1", "S-1/A"}
REPORTING_FORMS = {
    "8-K", "8-K/A",
    "8-K12B", "8-K12B/A",
    "8-K12G3", "8-K12G3/A",
    "8-K15D5", "8-K15D5/A",
    # Exchange Act registration statements are affirmative evidence that the
    # issuer entered the public reporting system before a later S-1/S-1A.
    "10-12B", "10-12B/A", "10-12G", "10-12G/A",
    "10-Q", "10-Q/A", "10-QT", "10-QT/A",
    "10-K", "10-K/A", "10-KT", "10-KT/A",
    # Rule 12b-25 late-filing notices for core periodic reports are affirmative
    # evidence that the issuer already had the corresponding Exchange Act
    # reporting obligation before a later S-1/S-1A candidate.
    "NT 10-Q", "NT 10-Q/A",
    "NT 10-K", "NT 10-K/A",
    "NT 20-F", "NT 20-F/A",
    # Legacy small-business Exchange Act registration and periodic-report forms
    # must not disappear as prior-public evidence for dormant/reactivated issuers.
    "10SB12B", "10SB12B/A", "10SB12G", "10SB12G/A",
    "10QSB", "10QSB/A",
    "10KSB", "10KSB/A", "10KSB40", "10KSB40/A",
    # Form 15 termination of a Section 12(b) or 12(g) registration proves a class
    # was previously Exchange Act registered. Deliberately omit 15-15D because a
    # Section 15(d) duty can arise from a Securities Act registration alone.
    "15-12B", "15-12B/A", "15-12G", "15-12G/A",
    "6-K", "6-K/A", "20-F", "20-F/A", "40-F", "40-F/A",
    # Foreign-private-issuer Exchange Act registration statements are the direct
    # counterparts to domestic Form 10 registration statements.
    "20FR12B", "20FR12B/A", "20FR12G", "20FR12G/A",
    "40FR12B", "40FR12B/A", "40FR12G", "40FR12G/A",
    # Registrant/management proxy and information statements are Exchange Act
    # filings for securities already registered under Section 12. Non-management
    # third-party proxy variants remain deliberately excluded.
    "PRE 14A", "DEF 14A", "PRE 14C", "DEF 14C",
    "DEFA14A", "DEFA14C",
    "DEFM14A", "DEFM14C",
    "DEFR14A", "DEFR14C",
    "PREM14A", "PREM14C",
    "PRER14A", "PRER14C",
    "S-3", "S-3/A", "S-3ASR", "S-3ASR/A", "S-3D", "S-3DPOS", "S-3MEF",
    "F-3", "F-3/A", "F-3ASR", "F-3ASR/A", "F-3D", "F-3DPOS", "F-3MEF",
    # A strictly prior final prospectus proves an earlier public offering already
    # completed and therefore the later S-1/S-1A is not a first IPO registration.
    "424B4",
}
_SEC_FILING_TIMEZONE = ZoneInfo("America/New_York")
RIGHTS_OFFERING_PATTERNS = (
    re.compile(
        r"\bright(?:s)? offering\b.{0,6000}\bnon[- ]?transferable\b.{0,500}\bsubscription rights\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\bnon[- ]?transferable\b.{0,500}\bsubscription rights\b.{0,6000}\bright(?:s)? offering\b",
        re.IGNORECASE | re.DOTALL,
    ),
)
EXISTING_PUBLIC_MARKET_PATTERNS = (
    re.compile(
        r"\bour\s+common\s+(?:stock|shares)\s+(?:is|are)\s+(?:currently\s+|presently\s+)?"
        r"(?:quoted|listed|traded)\s+on\s+(?:the\s+)?OTC[A-Z0-9]*\s+Market\b"
        r".{0,3000}\b(?:last\s+reported|last\s+sale|closing)\s+price\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(?:our\s+)?(?:common\s+)?(?:stock|shares)\s+(?:is|are)\s+(?:currently\s+|presently\s+)?"
        r"(?:quoted|listed|traded)\s+on\s+(?:the\s+)?OTC(?:QX|QB|ID|IQ)?\b"
        r".{0,3000}\b(?:last\s+reported|last\s+sale|closing)\s+price\b",
        re.IGNORECASE | re.DOTALL,
    ),
)
RIGHTS_OFFERING_EXCLUSION_REASON = (
    "current SEC registration is a non-transferable subscription-rights offering"
)
EXISTING_PUBLIC_MARKET_EXCLUSION_REASON = (
    "current SEC prospectus confirms a pre-existing public OTC trading market"
)


def _normalized_accession(value: str) -> str:
    return str(value or "").strip().replace("-", "")


def _iso_date(value):
    """Return a canonical SEC ISO filing date, otherwise None."""
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def _canonical_acceptance_datetime(value):
    """Return a comparable UTC SEC acceptance timestamp or None when ambiguous."""
    raw = str(value or "").strip()
    if not raw:
        return None

    if len(raw) == 14 and raw.isdigit():
        try:
            parsed = datetime.strptime(raw, "%Y%m%d%H%M%S").replace(
                tzinfo=_SEC_FILING_TIMEZONE
            )
        except ValueError:
            return None
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)

    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _strictly_precedes(candidate: dict, current: dict) -> bool:
    """Return True only when SEC chronology proves candidate preceded current."""
    candidate_date = _iso_date(candidate.get("filing_date"))
    current_date = _iso_date(current.get("filing_date"))
    if candidate_date is None or current_date is None:
        return False
    if candidate_date < current_date:
        return True
    if candidate_date > current_date:
        return False

    candidate_acceptance = _canonical_acceptance_datetime(
        candidate.get("acceptance_datetime")
    )
    current_acceptance = _canonical_acceptance_datetime(
        current.get("acceptance_datetime")
    )
    if candidate_acceptance is None or current_acceptance is None:
        return False
    return candidate_acceptance < current_acceptance


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
    acceptance_times = recent.get("acceptanceDateTime", []) or []
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
            "acceptance_datetime": (
                str(acceptance_times[i] or "").strip()
                if i < len(acceptance_times)
                else ""
            ),
        }
        for i in range(count)
    ]


def already_reporting_before_registration(record: dict) -> bool:
    """Return True when SEC history proves the issuer reported before this S-1.

    A prior Exchange Act report or an S-3/F-3-family short-form registration is
    affirmative evidence that the issuer was already subject to Exchange Act reporting.
    The chronology cutoff comes from the exact candidate accession in SEC submissions
    metadata, not the mutable public-feed date. Same-day history is accepted only when
    exact SEC acceptance timestamps prove that the reporting filing was earlier.
    """
    if str(record.get("form") or "").strip().upper() not in FORM_TYPES:
        return False
    if str(record.get("stage") or "").strip().casefold() != "pre-pricing":
        return False

    cik = str(record.get("cik") or "").strip()
    accession_no = str(record.get("accession_no") or "").strip()
    if not cik or not accession_no:
        return False

    try:
        rows = _recent_submission_rows(cik)
    except Exception as error:
        print(
            f"[s1_registration_history_gate] SEC reporting-history lookup failed for "
            f"{record.get('company') or cik}: {error}"
        )
        return False

    current_key = _normalized_accession(accession_no)
    current = next(
        (
            row for row in rows
            if _normalized_accession(row.get("accession_no")) == current_key
            and row.get("form") in FORM_TYPES
        ),
        None,
    )
    if current is None or _iso_date(current.get("filing_date")) is None:
        return False

    for row in rows:
        if row.get("form") not in REPORTING_FORMS:
            continue
        if _strictly_precedes(row, current):
            return True
    return False


def _same_registration_predecessors(cik: str, accession_no: str) -> list[dict]:
    """Return provably earlier S-1/S-1A filings sharing the SEC file number.

    Different-day SEC filing dates establish ordering. Same-day rows qualify only
    when authoritative SEC acceptance timestamps prove strict prior order. Missing,
    equal, malformed, or timezone-ambiguous same-day timing fails closed.
    """
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
    if not current_file_number or _iso_date(current.get("filing_date")) is None:
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
        if not _strictly_precedes(row, current):
            continue
        if not primary_document:
            continue
        predecessors.append({
            "accession_no": accession,
            "form": form,
            "file_number": file_number,
            "filing_date": filing_date,
            "primary_document": primary_document,
            "acceptance_datetime": str(row.get("acceptance_datetime") or "").strip(),
        })

    def predecessor_sort_key(row):
        return (
            _iso_date(row.get("filing_date")) or date.min,
            _canonical_acceptance_datetime(row.get("acceptance_datetime")) or datetime.min,
            row.get("accession_no", ""),
        )

    return sorted(predecessors, key=predecessor_sort_key, reverse=True)


def _primary_document_url(cik: str, filing: dict) -> str:
    folder = _normalized_accession(filing.get("accession_no"))
    document = str(filing.get("primary_document") or "").lstrip("/")
    return f"{edgar_client.EDGAR_ARCHIVES_BASE}/{int(cik)}/{folder}/{document}"


def _current_registration_front_text(record: dict):
    """Return normalized front-of-prospectus text for the exact current S-1 filing."""
    if str(record.get("form") or "").strip().upper() not in FORM_TYPES:
        return None
    if str(record.get("stage") or "").strip().casefold() != "pre-pricing":
        return None

    cik = str(record.get("cik") or "").strip()
    accession_no = str(record.get("accession_no") or record.get("id") or "").strip()
    if not cik or not accession_no:
        return None

    try:
        rows = _recent_submission_rows(cik)
        current_key = _normalized_accession(accession_no)
        current = next(
            (row for row in rows if _normalized_accession(row.get("accession_no")) == current_key),
            None,
        )
        if not current or not current.get("primary_document"):
            return None
        soup = filing_parser.fetch_document(_primary_document_url(cik, current))
        return " ".join(soup.get_text(" ", strip=True).split())[:125000]
    except Exception as error:
        print(
            f"[s1_registration_history_gate] Current filing lookup failed for "
            f"{record.get('company') or accession_no}: {error}"
        )
        return None


def current_registration_exclusion_reason(record: dict):
    """Return an explicit current-prospectus non-IPO reason, otherwise None."""
    normalized = _current_registration_front_text(record)
    if not normalized:
        return None
    if any(pattern.search(normalized) for pattern in RIGHTS_OFFERING_PATTERNS):
        return RIGHTS_OFFERING_EXCLUSION_REASON
    if any(pattern.search(normalized) for pattern in EXISTING_PUBLIC_MARKET_PATTERNS):
        return EXISTING_PUBLIC_MARKET_EXCLUSION_REASON
    return None


def current_registration_is_rights_offering(record: dict) -> bool:
    """Return True only when the current SEC registration explicitly is a rights offering."""
    return current_registration_exclusion_reason(record) == RIGHTS_OFFERING_EXCLUSION_REASON


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
    """Remove only the exact pre-pricing candidates proven to be non-IPOs."""
    s1_watch_path = Path(s1_watch_path)
    queue_path = Path(queue_path)
    watch_payload = _load_payload(s1_watch_path)
    queue_payload = _load_payload(queue_path)

    excluded_ciks = set()
    excluded_candidates = set()
    for record in _candidate_records(watch_payload, queue_payload):
        already_reporting = already_reporting_before_registration(record)
        transaction_reason = (
            None if already_reporting else current_registration_exclusion_reason(record)
        )
        resale_history = (
            False if (already_reporting or transaction_reason)
            else amendment_inherits_resale_exclusion(record)
        )
        if already_reporting or transaction_reason or resale_history:
            cik = str(record.get("cik") or "").zfill(10)
            if cik.strip("0"):
                excluded_ciks.add(cik)
                excluded_candidates.add(_candidate_identity(record))
                if already_reporting:
                    reason = "SEC reporting forms predate the candidate S-1/S-1A"
                elif transaction_reason:
                    reason = transaction_reason
                else:
                    reason = "prior filing in the same SEC registration statement is resale/direct-listing only"
                print(
                    f"[s1_registration_history_gate] Excluding "
                    f"{record.get('company') or cik}: {reason}"
                )

    if not excluded_candidates:
        print(
            "[s1_registration_history_gate] No reporting-history, current-prospectus, "
            "or resale exclusions found"
        )
        return set()

    def keep_row(row: dict) -> bool:
        if not _is_prepricing_s1(row):
            return True
        return _candidate_identity(row) not in excluded_candidates

    watch_payload["filings"] = [
        row for row in watch_payload.get("filings", [])
        if keep_row(row)
    ]
    queue_payload["filings"] = [
        row for row in queue_payload.get("filings", [])
        if keep_row(row)
    ]

    _write_payload(s1_watch_path, watch_payload)
    _write_payload(queue_path, queue_payload)
    write_dashboard_csv(queue_payload.get("filings", []), queue_path)
    return excluded_ciks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exclude pre-pricing rows with prior reporting, current non-IPO, or resale evidence"
    )
    parser.add_argument("s1_watch")
    parser.add_argument("queue")
    args = parser.parse_args()
    excluded = apply_gate(Path(args.s1_watch), Path(args.queue))
    print(f"[s1_registration_history_gate] Removed {len(excluded)} issuer(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
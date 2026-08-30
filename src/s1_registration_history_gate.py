"""Release gate for S-1/A amendments whose registration history is resale-only.

A current amendment can change formatting or cover wording enough to evade the
point-in-time resale classifier. SEC submissions metadata links amendments to the
same registration statement through ``fileNumber``. This gate checks earlier
S-1/S-1A filings in that exact registration lineage and excludes the current
pre-pricing row only when an earlier filing is deterministically resale/direct-
listing and the current record has no high-confidence issuer-primary offering
shares.

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


def _same_registration_predecessors(cik: str, accession_no: str) -> list[dict]:
    """Return earlier S-1/S-1A filings sharing the current SEC file number."""
    padded_cik = str(cik or "").zfill(10)
    if not padded_cik.strip("0") or not accession_no:
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

    current_key = _normalized_accession(accession_no)
    current_index = next(
        (i for i in range(count) if _normalized_accession(accessions[i]) == current_key),
        None,
    )
    if current_index is None:
        return []

    current_file_number = str(file_numbers[current_index] or "").strip()
    current_date = str(filing_dates[current_index] or "").strip()
    if not current_file_number:
        return []

    predecessors = []
    for i in range(count):
        accession = str(accessions[i] or "").strip()
        form = str(forms[i] or "").strip().upper()
        file_number = str(file_numbers[i] or "").strip()
        filing_date = str(filing_dates[i] or "").strip()
        primary_document = str(primary_documents[i] or "").strip()
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


def apply_gate(s1_watch_path: Path, queue_path: Path) -> set[str]:
    """Remove confirmed resale-lineage amendments from pre-pricing outputs."""
    s1_watch_path = Path(s1_watch_path)
    queue_path = Path(queue_path)
    watch_payload = _load_payload(s1_watch_path)
    queue_payload = _load_payload(queue_path)

    excluded_ciks = set()
    for record in watch_payload.get("filings", []):
        if amendment_inherits_resale_exclusion(record):
            cik = str(record.get("cik") or "").zfill(10)
            if cik.strip("0"):
                excluded_ciks.add(cik)
                print(
                    f"[s1_registration_history_gate] Excluding "
                    f"{record.get('company') or cik}: prior filing in the same "
                    f"SEC registration statement is resale/direct-listing only"
                )

    if not excluded_ciks:
        print("[s1_registration_history_gate] No same-registration resale exclusions found")
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
        description="Exclude S-1/A rows with authoritative same-registration resale history"
    )
    parser.add_argument("s1_watch")
    parser.add_argument("queue")
    args = parser.parse_args()
    excluded = apply_gate(Path(args.s1_watch), Path(args.queue))
    print(f"[s1_registration_history_gate] Removed {len(excluded)} issuer(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

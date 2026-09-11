"""Confirm S-1/S-1A -> 424B4 registration lineage from SEC submissions.

Lifecycle reconciliation must not promote a pre-pricing row merely because a later
424B4 shares the same issuer CIK. Issuers can have multiple registrations, including
resale and follow-on offerings. This module requires the exact S-1/S-1A and 424B4
accessions to share the SEC-assigned registration file number before a promotion is
allowed.
"""

from __future__ import annotations

from datetime import datetime
import re

import edgar_client


_ARCHIVE_BASE = "https://data.sec.gov/submissions"
_REQUIRED_FIELDS = ("accessionNumber", "form", "fileNumber", "filingDate")


def _canonical_cik(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.zfill(10) if digits else ""


def _canonical_accession(value):
    return re.sub(r"\D", "", str(value or ""))


def _canonical_date(value):
    raw = str(value or "").strip()
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def _rows_from_block(block):
    """Return aligned SEC filing rows, rejecting malformed array structures."""
    if not isinstance(block, dict):
        raise ValueError("SEC submissions filing block must be an object")

    arrays = {field: block.get(field) for field in _REQUIRED_FIELDS}
    if any(not isinstance(values, list) for values in arrays.values()):
        raise ValueError("SEC submissions filing block is missing required arrays")

    lengths = {len(values) for values in arrays.values()}
    if len(lengths) != 1:
        raise ValueError("SEC submissions filing arrays are not aligned")

    rows = []
    row_count = next(iter(lengths), 0)
    for index in range(row_count):
        rows.append({
            "accession_no": str(arrays["accessionNumber"][index] or "").strip(),
            "form": str(arrays["form"][index] or "").strip().upper(),
            "file_number": str(arrays["fileNumber"][index] or "").strip(),
            "filing_date": str(arrays["filingDate"][index] or "").strip(),
        })
    return rows


def _required_accessions_found(rows, required_accessions):
    found = {
        _canonical_accession(row.get("accession_no"))
        for row in rows
        if _canonical_accession(row.get("accession_no"))
    }
    return set(required_accessions).issubset(found)


def load_registration_rows(cik, required_accessions=()):
    """Load exact SEC registration rows, traversing submissions archives as needed."""
    canonical_cik = _canonical_cik(cik)
    if not canonical_cik:
        raise ValueError("Registration-lineage lookup requires an exact issuer CIK")

    required = {
        _canonical_accession(value)
        for value in required_accessions
        if _canonical_accession(value)
    }
    headers = edgar_client._get_headers()
    data = edgar_client._request_json(
        edgar_client.EDGAR_SUBMISSIONS_URL.format(cik=canonical_cik),
        headers,
    )
    filings = data.get("filings") or {}
    recent = filings.get("recent") or {}
    rows = _rows_from_block(recent)

    if not required or _required_accessions_found(rows, required):
        return rows

    archives = filings.get("files") or []
    if not isinstance(archives, list):
        raise ValueError("SEC submissions archive list is malformed")

    for descriptor in archives:
        if not isinstance(descriptor, dict):
            continue
        name = str(descriptor.get("name") or "").strip()
        if not name:
            continue
        archive = edgar_client._request_json(f"{_ARCHIVE_BASE}/{name}", headers)
        rows.extend(_rows_from_block(archive))
        if _required_accessions_found(rows, required):
            break

    return rows


def build_registration_lineage_resolver(rows_loader=load_registration_rows):
    """Return a cached exact-accession resolver for S-1/S-1A -> 424B4 lineage.

    Exact accession and file-number identity are necessary but not sufficient for a
    release-grade lifecycle handoff. The published pre-pricing filing date must also
    agree with the SEC date for that exact S-1/S-1A accession, just as the candidate
    424B4 date is verified. This prevents stale or corrupted row chronology from
    being carried into a priced record under otherwise-valid registration lineage.

    Only SEC registration evidence is cached. Published-row dates are validated on
    every call so one valid row cannot cause a stale duplicate with the same accession
    pair to inherit a cached True result, and one stale row cannot poison a later valid
    row for the same exact SEC filings.
    """
    cache = {}

    def resolve(prepricing, final_meta):
        prepricing_cik = _canonical_cik((prepricing or {}).get("cik"))
        final_cik = _canonical_cik((final_meta or {}).get("cik"))
        if not prepricing_cik or prepricing_cik != final_cik:
            return False

        prepricing_accession = _canonical_accession(
            (prepricing or {}).get("accession_no") or (prepricing or {}).get("id")
        )
        final_accession = _canonical_accession((final_meta or {}).get("accession_no"))
        if not prepricing_accession or not final_accession:
            return False

        cache_key = (prepricing_cik, prepricing_accession, final_accession)
        if cache_key not in cache:
            try:
                rows = rows_loader(
                    prepricing_cik,
                    (prepricing_accession, final_accession),
                )
            except Exception:
                cache[cache_key] = (False, None, None)
            else:
                prepricing_rows = [
                    row
                    for row in rows
                    if _canonical_accession(row.get("accession_no")) == prepricing_accession
                ]
                final_rows = [
                    row
                    for row in rows
                    if _canonical_accession(row.get("accession_no")) == final_accession
                ]
                if len(prepricing_rows) != 1 or len(final_rows) != 1:
                    cache[cache_key] = (False, None, None)
                else:
                    s1_row = prepricing_rows[0]
                    final_row = final_rows[0]
                    s1_form = str(s1_row.get("form") or "").strip().upper()
                    final_form = str(final_row.get("form") or "").strip().upper()
                    s1_file_number = str(s1_row.get("file_number") or "").strip()
                    final_file_number = str(final_row.get("file_number") or "").strip()
                    s1_date = _canonical_date(s1_row.get("filing_date"))
                    final_date = _canonical_date(final_row.get("filing_date"))
                    sec_lineage_valid = bool(
                        s1_form in {"S-1", "S-1/A"}
                        and final_form == "424B4"
                        and s1_file_number
                        and final_file_number
                        and s1_file_number == final_file_number
                        and s1_date is not None
                        and final_date is not None
                        and final_date >= s1_date
                    )
                    cache[cache_key] = (sec_lineage_valid, s1_date, final_date)

        sec_lineage_valid, s1_date, final_date = cache[cache_key]
        prepricing_date = _canonical_date(
            (prepricing or {}).get("filed")
            or (prepricing or {}).get("filing_date")
        )
        candidate_date = _canonical_date((final_meta or {}).get("filing_date"))
        return bool(
            sec_lineage_valid
            and prepricing_date is not None
            and candidate_date is not None
            and prepricing_date == s1_date
            and candidate_date == final_date
        )

    return resolve

"""Recover exact SEC metadata for published 424B4 rows outside discovery windows.

The rolling 424B4 search is intentionally bounded for new-filing discovery. Published
final IPOs, however, remain release-critical after their prospectuses age out of that
window. Rehydrate only exact CIK+accession identities from SEC submissions history so
lifecycle reconciliation can continue to recheck authoritative final terms without
falling back to issuer, ticker, or date proximity.
"""

from __future__ import annotations

from datetime import datetime
import re

import registration_lineage


def _canonical_cik(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.zfill(10) if digits else ""


def _canonical_accession(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == 18 else ""


def _canonical_date(value):
    raw = str(value or "").strip()
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return ""
    return raw if parsed.isoformat() == raw else ""


def _candidate_key(meta):
    if not isinstance(meta, dict):
        return ("", "")
    return (
        _canonical_cik(meta.get("cik")),
        _canonical_accession(meta.get("accession_no")),
    )


def augment_published_final_metadata(payload, final_filings, rows_loader=None):
    """Add exact SEC metadata for published finals missing from the rolling snapshot.

    A transient SEC submissions failure leaves the already-published row untouched for
    this cycle. Once SEC history is returned successfully, missing, duplicate, wrong-
    form, or malformed exact-accession evidence is release-blocking rather than guessed.
    """
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("Public feed must contain a filings list")
    if not isinstance(final_filings, list):
        raise ValueError("Final-filings snapshot must be a list")

    loader = rows_loader or registration_lineage.load_registration_rows
    augmented = list(final_filings)
    existing = {
        key
        for key in (_candidate_key(meta) for meta in augmented)
        if all(key)
    }

    missing_by_cik = {}
    for record in filings:
        if not isinstance(record, dict):
            continue
        if str(record.get("form") or "").strip().upper() != "424B4":
            continue

        cik = _canonical_cik(record.get("cik"))
        accession = _canonical_accession(record.get("accession_no"))
        if not cik or not accession:
            raise RuntimeError(
                "Published 424B4 lacks an exact CIK/accession identity; refusing "
                "historical lifecycle metadata recovery"
            )
        if (cik, accession) in existing:
            continue
        missing_by_cik.setdefault(cik, {})[accession] = record

    for cik, records_by_accession in missing_by_cik.items():
        required = tuple(records_by_accession)
        try:
            rows = loader(cik, required)
        except Exception as error:
            print(
                "[published_final_history] SEC submissions history unavailable for "
                f"CIK {cik}; preserving published finals without historical recheck "
                f"this cycle: {error}"
            )
            continue

        if not isinstance(rows, list):
            raise RuntimeError(
                f"SEC submissions history returned malformed rows for CIK {cik}"
            )

        rows_by_accession = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            accession = _canonical_accession(row.get("accession_no"))
            if accession:
                rows_by_accession.setdefault(accession, []).append(row)

        for accession, record in records_by_accession.items():
            matches = rows_by_accession.get(accession) or []
            label = record.get("company") or cik
            if len(matches) != 1:
                raise RuntimeError(
                    "Published 424B4 exact accession could not be uniquely confirmed "
                    f"in SEC submissions history for {label}"
                )

            row = matches[0]
            if str(row.get("form") or "").strip().upper() != "424B4":
                raise RuntimeError(
                    "Published final accession is not a 424B4 in SEC submissions "
                    f"history for {label}"
                )
            filing_date = _canonical_date(row.get("filing_date"))
            if not filing_date:
                raise RuntimeError(
                    "Published 424B4 has no canonical SEC filing date in submissions "
                    f"history for {label}"
                )

            raw_accession = str(row.get("accession_no") or "").strip()
            augmented.append(
                {
                    "company_name": str(record.get("company") or "").strip(),
                    # SEC submissions history does not establish a listing symbol.
                    # Leave this blank so lifecycle repair must inspect the exact
                    # final prospectus before a stored ticker/quote can survive.
                    "ticker": None,
                    "cik": cik,
                    "accession_no": raw_accession,
                    "filing_date": filing_date,
                    "form_type": "424B4",
                }
            )
            existing.add((cik, accession))

    return augmented

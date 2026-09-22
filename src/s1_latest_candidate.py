"""Resolve the authoritative latest S-1/S-1A candidate for each issuer.

SEC daily master indexes provide filing dates but not acceptance times. Multiple
registration statements can therefore share the same filing date, and neither form
precedence nor discovery order is authoritative chronology. For same-day candidates,
load the exact SEC submissions rows and require unique acceptance timestamps before
allowing one filing to decide the issuer's current pre-pricing state.
"""

from __future__ import annotations

import re

import registration_lineage


FORM_TYPES = {"S-1", "S-1/A"}


def _canonical_cik(value) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.zfill(10) if digits else ""


def _canonical_accession(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _canonical_date(value) -> str:
    raw = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return ""
    try:
        from datetime import date

        parsed = date.fromisoformat(raw)
    except ValueError:
        return ""
    return raw if parsed.isoformat() == raw else ""


def resolve_latest_positions(evaluations, rows_loader=None):
    """Return ``(latest_by_cik, unresolved_ciks)`` for S-1 monitor evaluations.

    Different-day candidates are ordered by their canonical SEC filing date without
    an extra network request. If two or more candidates for the same issuer share the
    newest filing date, exact SEC submissions history must prove their order using
    ``acceptanceDateTime``. Any missing, duplicate, malformed, form/date-mismatched,
    or tied acceptance evidence fails closed for that issuer so prior published state
    can be preserved instead of being replaced by a guessed filing.
    """
    loader = rows_loader or registration_lineage.load_registration_rows
    grouped = {}
    unresolved = set()

    for position, (meta, _record, _evaluated) in enumerate(evaluations or []):
        meta = meta if isinstance(meta, dict) else {}
        cik = _canonical_cik(meta.get("cik"))
        if not cik:
            continue
        filed = _canonical_date(meta.get("filing_date"))
        form = str(meta.get("form_type") or "").strip().upper()
        accession = _canonical_accession(meta.get("accession_no"))
        if not filed or form not in FORM_TYPES:
            unresolved.add(cik)
            continue
        grouped.setdefault(cik, []).append(
            {
                "position": position,
                "filed": filed,
                "form": form,
                "accession": accession,
            }
        )

    latest_by_cik = {}
    for cik, entries in grouped.items():
        if cik in unresolved:
            continue

        latest_date = max(entry["filed"] for entry in entries)
        same_day = [entry for entry in entries if entry["filed"] == latest_date]
        if len(same_day) == 1:
            latest_by_cik[cik] = same_day[0]["position"]
            continue

        accessions = [entry["accession"] for entry in same_day]
        if any(not accession for accession in accessions) or len(set(accessions)) != len(accessions):
            unresolved.add(cik)
            continue

        try:
            rows = loader(cik, tuple(accessions))
        except Exception:
            unresolved.add(cik)
            continue
        if not isinstance(rows, list):
            unresolved.add(cik)
            continue

        rows_by_accession = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            accession = _canonical_accession(row.get("accession_no"))
            if accession:
                rows_by_accession.setdefault(accession, []).append(row)

        ordered = []
        valid = True
        for entry in same_day:
            matches = rows_by_accession.get(entry["accession"]) or []
            if len(matches) != 1:
                valid = False
                break
            row = matches[0]
            if str(row.get("form") or "").strip().upper() != entry["form"]:
                valid = False
                break
            if _canonical_date(row.get("filing_date")) != entry["filed"]:
                valid = False
                break
            accepted = registration_lineage._canonical_acceptance_datetime(
                row.get("acceptance_datetime")
            )
            if accepted is None:
                valid = False
                break
            ordered.append((accepted, entry["position"]))

        if not valid:
            unresolved.add(cik)
            continue

        latest_acceptance = max(accepted for accepted, _position in ordered)
        winners = [
            position
            for accepted, position in ordered
            if accepted == latest_acceptance
        ]
        if len(winners) != 1:
            unresolved.add(cik)
            continue
        latest_by_cik[cik] = winners[0]

    return latest_by_cik, unresolved

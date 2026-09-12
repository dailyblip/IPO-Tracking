"""Protect exact SEC accession identity before 424B4 lifecycle reconciliation.

A published final record is an exact SEC filing identity, not merely an issuer-CIK
state. The public feed normally stores that accession in both ``id`` and
``accession_no``. If the duplicate ``accession_no`` field is lost during an older
feed merge, lifecycle code must not fall back to an arbitrary 424B4 under the same
CIK. Recover the accession only from an accession-shaped record ``id`` and fail
closed when a final record has no exact filing identity or contains conflicting
accession identities.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import dashboard_export


_DASHED_ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
_UNDASHED_ACCESSION = re.compile(r"^\d{18}$")


def _accession_identity(value):
    """Return the 18-digit canonical SEC accession only for accession-shaped input."""
    text = str(value or "").strip()
    if _DASHED_ACCESSION.fullmatch(text):
        return text.replace("-", "")
    if _UNDASHED_ACCESSION.fullmatch(text):
        return text
    return ""


def repair_final_accession_identities(payload):
    """Repair or reject ambiguous published 424B4 identities.

    ``dashboard_export`` keys normal SEC final rows by accession, so an
    accession-shaped ``id`` is authoritative duplicate provenance when the explicit
    ``accession_no`` field is blank. A final with neither identity cannot safely be
    reconciled against another filing under the same CIK and therefore blocks
    release instead of being guessed from issuer/date proximity.
    """
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("Public feed must contain a filings list")

    repaired = 0
    normalized = []
    for filing in filings:
        if not isinstance(filing, dict) or str(filing.get("form") or "").upper() != "424B4":
            normalized.append(filing)
            continue

        accession_raw = str(filing.get("accession_no") or "").strip()
        accession = _accession_identity(accession_raw)
        row_id_raw = str(filing.get("id") or "").strip()
        row_id = _accession_identity(row_id_raw)

        if accession_raw and not accession:
            raise RuntimeError(
                "Final 424B4 has a malformed SEC accession_no; refusing ambiguous "
                f"lifecycle reconciliation for {filing.get('company') or filing.get('cik') or 'unknown issuer'}"
            )

        if accession and row_id and accession != row_id:
            raise RuntimeError(
                "Final 424B4 has conflicting SEC accession identities in id/accession_no; "
                f"refusing lifecycle reconciliation for {filing.get('company') or filing.get('cik') or 'unknown issuer'}"
            )

        if accession:
            normalized.append(filing)
            continue

        if not row_id:
            raise RuntimeError(
                "Final 424B4 lacks an exact SEC accession identity; refusing CIK-only "
                f"lifecycle reconciliation for {filing.get('company') or filing.get('cik') or 'unknown issuer'}"
            )

        updated = dict(filing)
        updated["accession_no"] = row_id_raw
        normalized.append(updated)
        repaired += 1

    current = dict(payload)
    current["filings"] = normalized
    if repaired:
        current["generated_at"] = datetime.now(timezone.utc).isoformat()
    return current, repaired


def repair_feed(output_path):
    output_path = Path(output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    repaired_payload, repaired = repair_final_accession_identities(payload)

    if repaired:
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(repaired_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)

    dashboard_export.write_dashboard_csv(repaired_payload.get("filings", []), output_path)
    return repaired_payload, repaired


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../docs/data/filings.json")
    _, repaired_count = repair_feed(target)
    print(
        "Final accession identity guard repaired "
        f"{repaired_count} missing accession field(s); all final identities are exact."
    )

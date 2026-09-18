#!/usr/bin/env python3
"""Release gate for exact final-prospectus accession identity.

All published 424B4/Priced rows must retain an SEC accession identity.  The
public feed normally stores that accession in both ``id`` and
``accession_no``; older lifecycle passes could occasionally lose the
duplicated ``accession_no`` value while preserving the accession-shaped
``id``.

This gate repairs only deterministic duplicate loss and canonical accession
formatting.  If a published final row has no exact accession source, or has
conflicting accession identities, publication is blocked rather than
inferring identity from CIK/ticker/company/date proximity.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_DASHED_ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
_UNDASHED_ACCESSION = re.compile(r"^\d{18}$")


def _is_published_final(filing: Dict[str, Any]) -> bool:
    return str(filing.get("form_type") or "").strip().upper() == "424B4" or str(
        filing.get("stage") or ""
    ).strip().lower() == "priced"


def _accession_identity(value: Any) -> str:
    text = str(value or "").strip()
    if _DASHED_ACCESSION.fullmatch(text):
        return text.replace("-", "")
    if _UNDASHED_ACCESSION.fullmatch(text):
        return text
    return ""


def _dashed_accession(identity: str) -> str:
    if not _UNDASHED_ACCESSION.fullmatch(identity):
        return ""
    return f"{identity[:10]}-{identity[10:12]}-{identity[12:]}"


def repair_or_reject_final_identity(
    payload: Dict[str, Any],
) -> Tuple[Dict[str, Any], int]:
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise RuntimeError("feed payload is missing a filings list")

    repaired = 0
    normalized: List[Any] = []
    defects: List[str] = []

    for filing in filings:
        if not isinstance(filing, dict) or not _is_published_final(filing):
            normalized.append(filing)
            continue

        accession_value = str(filing.get("accession_no") or "")
        accession_raw = accession_value.strip()
        row_id_raw = str(filing.get("id") or "").strip()
        accession = _accession_identity(accession_raw)
        row_id = _accession_identity(row_id_raw)

        label = (
            str(filing.get("company_name") or filing.get("cik") or row_id_raw or "unknown")
            .strip()
        )

        if accession and row_id and accession != row_id:
            defects.append(
                f"{label}: conflicting final accession identities "
                f"(id={row_id_raw!r}, accession_no={accession_raw!r})"
            )
            normalized.append(filing)
            continue

        if accession:
            canonical_accession = _dashed_accession(accession)
            if accession_value != canonical_accession:
                updated = dict(filing)
                updated["accession_no"] = canonical_accession
                normalized.append(updated)
                repaired += 1
            else:
                normalized.append(filing)
            continue

        if accession_raw:
            defects.append(
                f"{label}: invalid final accession_no {accession_raw!r}; "
                "refusing to infer a replacement"
            )
            normalized.append(filing)
            continue

        if row_id:
            updated = dict(filing)
            updated["accession_no"] = _dashed_accession(row_id)
            normalized.append(updated)
            repaired += 1
            continue

        defects.append(
            f"{label}: published final record has no exact SEC accession identity"
        )
        normalized.append(filing)

    if defects:
        preview = "; ".join(defects[:5])
        if len(defects) > 5:
            preview += f"; ... +{len(defects) - 5} more"
        raise RuntimeError(
            "release blocked: published 424B4/Priced accession identity defects: "
            + preview
        )

    updated_payload = dict(payload)
    updated_payload["filings"] = normalized
    return updated_payload, repaired


def load_feed(path: Path) -> Dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError("feed root must be an object")
    return loaded


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Repair or reject exact accession identity on published final rows"
    )
    parser.add_argument(
        "--feed",
        type=Path,
        default=Path("docs/data/filings.json"),
        help="published feed JSON path",
    )
    args = parser.parse_args(argv)

    try:
        payload = load_feed(args.feed)
        updated, repaired = repair_or_reject_final_identity(payload)
    except Exception as exc:
        print(f"Final accession identity guard failed: {exc}")
        return 1

    if repaired:
        args.feed.write_text(
            json.dumps(updated, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        print(f"Repaired exact accession identity for {repaired} published final row(s).")
    else:
        print("Final accession identity guard passed with no repairs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Fail closed on non-substantive Form S-1 template filings.

Research Monitor publishes confirmed operating-company IPO registrations, not bare
administrative Form S-1 shells. A filing that contains only the SEC form template,
placeholder fee-table values, and signature/instruction boilerplate is not yet
affirmative public evidence of a substantive IPO prospectus.

This gate is deliberately narrow. It does not require a price, ticker, offering
size, or underwriter, and it does not exclude an otherwise substantive early IPO
registration simply because economics are still blank. Network/parser failures do
not create an exclusion; the filing remains available for later authoritative
reconciliation.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import dashboard_export
import filing_parser

FORM_TYPES = {"S-1", "S-1/A"}

_TEMPLATE_MARKERS = (
    re.compile(r"\bFORM\s+S-1\b", re.IGNORECASE),
    re.compile(r"\bREGISTRATION\s+STATEMENT\s+UNDER\s+THE\s+SECURITIES\s+ACT\s+OF\s+1933\b", re.IGNORECASE),
    re.compile(r"\bCALCULATION\s+OF\s+FILING\s+FEE\s+TABLES?\b", re.IGNORECASE),
    re.compile(r"\bFEES?\s+TO\s+BE\s+PAID\b", re.IGNORECASE),
    re.compile(r"\bSIGNATURES?\b", re.IGNORECASE),
)
_PLACEHOLDER_PATTERN = re.compile(r"(?:\bX\b[\s,;|]*){5,}", re.IGNORECASE)
_SUBSTANTIVE_PROSPECTUS_PATTERNS = (
    re.compile(r"\bPROSPECTUS\b", re.IGNORECASE),
    re.compile(r"\bINITIAL\s+PUBLIC\s+OFFERING\b", re.IGNORECASE),
    re.compile(r"\bWE\s+ARE\s+OFFERING\b", re.IGNORECASE),
    re.compile(r"\bUNDERWRITERS?\b", re.IGNORECASE),
    re.compile(r"\bRISK\s+FACTORS\b", re.IGNORECASE),
    re.compile(r"\bUSE\s+OF\s+PROCEEDS\b", re.IGNORECASE),
)


def is_non_substantive_template_text(text: str) -> bool:
    """Return True only for a short SEC S-1 shell with placeholder form content."""
    normalized = " ".join(str(text or "").split())
    if not normalized or len(normalized) > 12000:
        return False
    if not all(pattern.search(normalized) for pattern in _TEMPLATE_MARKERS):
        return False
    if not _PLACEHOLDER_PATTERN.search(normalized):
        return False
    if any(pattern.search(normalized) for pattern in _SUBSTANTIVE_PROSPECTUS_PATTERNS):
        return False
    return True


def _fetch_current_text(record: dict) -> str:
    sec_url = str(record.get("sec_url") or "").strip()
    form = str(record.get("form") or "").strip().upper()
    if not sec_url or form not in FORM_TYPES:
        return ""
    document_url = filing_parser.find_primary_document_url(
        sec_url,
        expected_form_types=[form],
    )
    soup = filing_parser.fetch_document(document_url)
    return soup.get_text(" ", strip=True)


def current_registration_is_non_substantive_template(record: dict) -> bool:
    if str(record.get("form") or "").strip().upper() not in FORM_TYPES:
        return False
    if str(record.get("stage") or "").strip().casefold() != "pre-pricing":
        return False
    try:
        return is_non_substantive_template_text(_fetch_current_text(record))
    except Exception as error:
        print(
            "[s1_substantive_registration_gate] Current filing inspection failed for "
            f"{record.get('company') or record.get('id') or '<unknown>'}: {error}"
        )
        return False


def _load_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_payload(path: Path, payload: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def _candidate_records(*payloads: dict) -> list[dict]:
    candidates = []
    seen = set()
    for payload in payloads:
        for record in payload.get("filings", []) if isinstance(payload, dict) else []:
            if not isinstance(record, dict):
                continue
            if str(record.get("stage") or "").strip().casefold() != "pre-pricing":
                continue
            if str(record.get("form") or "").strip().upper() not in FORM_TYPES:
                continue
            identity = (
                str(record.get("cik") or "").zfill(10),
                str(record.get("accession_no") or record.get("id") or "").replace("-", ""),
            )
            if identity in seen:
                continue
            seen.add(identity)
            candidates.append(record)
    return candidates


def apply_gate(s1_watch_path: Path, queue_path: Path) -> set[str]:
    """Remove only confirmed non-substantive template registrations from outputs."""
    s1_watch_path = Path(s1_watch_path)
    queue_path = Path(queue_path)
    watch_payload = _load_payload(s1_watch_path)
    queue_payload = _load_payload(queue_path)

    excluded_ciks = set()
    for record in _candidate_records(watch_payload, queue_payload):
        if not current_registration_is_non_substantive_template(record):
            continue
        cik = str(record.get("cik") or "").zfill(10)
        if not cik.strip("0"):
            continue
        excluded_ciks.add(cik)
        print(
            "[s1_substantive_registration_gate] Excluding "
            f"{record.get('company') or cik}: current SEC registration is a "
            "non-substantive Form S-1 template without affirmative IPO prospectus evidence"
        )

    if not excluded_ciks:
        print("[s1_substantive_registration_gate] No non-substantive S-1 templates found")
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
    dashboard_export.write_dashboard_csv(queue_payload.get("filings", []), queue_path)
    return excluded_ciks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exclude non-substantive SEC Form S-1 template filings from pre-pricing outputs"
    )
    parser.add_argument("s1_watch")
    parser.add_argument("queue")
    args = parser.parse_args()
    apply_gate(Path(args.s1_watch), Path(args.queue))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Reconcile pre-pricing S-1 tickers from explicit current listing language.

SEC submissions metadata can retain a stale historical ticker for a returning
issuer. For the pre-pricing watch, prefer the issuer's current S-1/S-1A
statement that it has applied, intends, or expects to list the offered shares
under a specific symbol. When a later amendment omits that statement, preserve
an earlier symbol only when exact-CIK, strictly earlier S-1/S-1A filing evidence
in the same SEC registration file-number lineage was successfully inspected and
is unambiguous. Absent or conflicting registration-lineage evidence fails closed
for a nonblank symbol.

When the CLI is invoked on ``s1_watch.json``, reconcile the sibling public
``filings.json`` queue as well. The queue may contain only the latest S-1 row,
so an exact CIK+accession ticker verified in the watch is allowed to carry into
that same queue record. If the queue changes, keep its companion CSV in sync so
a stale SEC-submissions ticker cannot survive in one public surface after being
corrected in another.
"""

import json
import re
import sys
from pathlib import Path

import dashboard_export
import filing_parser
import registration_lineage


_CURRENT_LISTING_PATTERNS = [
    r"\bwe\s+(?:have\s+|has\s+)?applied\s+to\s+list\b.{0,600}?"
    r"\bunder\s+(?:the\s+)?(?:ticker\s+|trading\s+)?symbol\s*[\"'“‘]?([A-Z](?:[A-Z0-9.-]{0,8}[A-Z0-9])?)[\"'”’]?",
    r"\bapplication\s+(?:has\s+been|is)\s+(?:made|submitted)\s+(?:to|for)\s+(?:list|listing)\b.{0,600}?"
    r"\bunder\s+(?:the\s+)?(?:ticker\s+|trading\s+)?symbol\s*[\"'“‘]?([A-Z](?:[A-Z0-9.-]{0,8}[A-Z0-9])?)[\"'”’]?",
    r"\bwe\s+(?:intend|expect|plan)\s+to\s+(?:list|trade)\b.{0,600}?"
    r"\bunder\s+(?:the\s+)?(?:ticker\s+|trading\s+)?symbol\s*[\"'“‘]?([A-Z](?:[A-Z0-9.-]{0,8}[A-Z0-9])?)[\"'”’]?",
    r"\b(?:our\s+common\s+stock|the\s+common\s+stock|our\s+shares|the\s+shares)\s+"
    r"(?:has|have)\s+been\s+(?:approved|authorized)\s+for\s+listing\b.{0,600}?"
    r"\bunder\s+(?:the\s+)?(?:ticker\s+|trading\s+)?symbol\s*[\"'“‘]?([A-Z](?:[A-Z0-9.-]{0,8}[A-Z0-9])?)[\"'”’]?",
]

_REGISTRATION_FILE_NUMBER_KEY = "_registration_file_number"


def extract_current_listing_tickers(text: str) -> set[str]:
    """Return current-offering ticker candidates supported by filing text."""
    tickers = set()
    text = str(text or "")
    for pattern in _CURRENT_LISTING_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
            ticker = match.group(1)
            # IGNORECASE is needed for prose, but a disclosed market symbol
            # should itself appear as an uppercase symbol in the filing.
            if ticker == ticker.upper():
                tickers.add(ticker)
    return tickers


def _fetch_filing_text(record: dict) -> str:
    sec_url = str(record.get("sec_url") or "").strip()
    form = str(record.get("form") or "").strip().upper()
    if not sec_url or form not in {"S-1", "S-1/A"}:
        return ""
    document_url = filing_parser.find_primary_document_url(
        sec_url, expected_form_types=[form]
    )
    soup = filing_parser.fetch_document(document_url)
    # The authoritative current-listing statement can occur well beyond the
    # first 100k characters in a long registration statement. We already have
    # the full filing in memory, so scan all filing text rather than allowing a
    # prefix cutoff to preserve a stale SEC-submissions ticker.
    return soup.get_text(" ", strip=True)


def _normalized_cik(record: dict) -> str:
    raw = str(record.get("cik") or "").strip()
    if not raw:
        return ""
    return raw.zfill(10)


def _accession(record: dict) -> str:
    return str(record.get("accession_no") or record.get("id") or "").strip()


def _normalized_accession(value: str) -> str:
    return str(value or "").strip().replace("-", "")


def _filed(record: dict) -> str:
    value = str(record.get("filed") or record.get("filing_date") or "").strip()
    return value if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else ""


def _record_key(record: dict) -> tuple[str, str]:
    return _normalized_cik(record), _accession(record)


def _verified_watch_tickers(payload: dict) -> dict[tuple[str, str], str]:
    """Return exact-record ticker evidence already reconciled in the watch."""
    verified = {}
    for record in payload.get("filings", []):
        if not isinstance(record, dict):
            continue
        if str(record.get("form") or "").strip().upper() not in {"S-1", "S-1/A"}:
            continue
        key = _record_key(record)
        ticker = str(record.get("ticker") or "").strip().upper()
        if key[0] and key[1] and ticker:
            verified[key] = ticker
    return verified


def _registration_file_numbers(records: list[dict]) -> dict[tuple[str, str], str]:
    """Return SEC registration file numbers for exact CIK+accession records.

    The SEC submissions feed is authoritative for ``fileNumber`` lineage. The
    archive-capable loader receives every required accession so registrations
    that have aged out of ``filings.recent`` are still resolved exactly. A
    lookup failure or missing accession intentionally leaves the record unmapped;
    callers then fail closed instead of carrying a ticker across an unproven
    registration relationship.
    """
    wanted_by_cik: dict[str, dict[str, tuple[str, str]]] = {}
    for record in records:
        key = _record_key(record)
        normalized_accession = _normalized_accession(key[1])
        if not key[0] or not normalized_accession:
            continue
        wanted_by_cik.setdefault(key[0], {})[normalized_accession] = key

    lineage: dict[tuple[str, str], str] = {}
    for cik, wanted in wanted_by_cik.items():
        try:
            submission_rows = registration_lineage.load_registration_rows(
                cik, tuple(wanted)
            )
        except Exception as error:
            print(
                f"[ticker_listing_reconciler] Warning: SEC registration-lineage "
                f"lookup failed for CIK {cik}: {error}"
            )
            continue

        for row in submission_rows:
            accession = _normalized_accession(row.get("accession_no"))
            file_number = str(row.get("file_number") or "").strip()
            original_key = wanted.get(accession)
            if original_key and file_number:
                lineage[original_key] = file_number

    return lineage


def reconcile_payload(
    payload: dict,
    fetch_text=_fetch_filing_text,
    verified_lineage: dict[tuple[str, str], str] | None = None,
) -> tuple[int, int]:
    """Reconcile S-1 tickers in place; return ``(updated, conflicts)``.

    Current filing language always controls. If a successfully inspected later
    amendment omits the listing statement, an earlier exact-CIK S-1/S-1A symbol
    may carry forward only when every inspectable prior symbol agrees and no prior
    filing in that lineage failed inspection. Production file reconciliation
    additionally annotates exact SEC ``fileNumber`` lineage; when present, only
    filings in that exact registration statement may seed carry-forward. Same-day
    filings inside the same registration statement are never ordered by inference.
    ``verified_lineage`` is reserved for the exact same CIK+accession already
    reconciled in ``s1_watch.json`` before the public queue is processed.
    """
    records = [
        record
        for record in payload.get("filings", [])
        if isinstance(record, dict)
        and str(record.get("form") or "").strip().upper() in {"S-1", "S-1/A"}
        and str(record.get("sec_url") or "").strip()
    ]
    verified_lineage = verified_lineage or {}
    strict_registration_lineage = any(
        _REGISTRATION_FILE_NUMBER_KEY in record for record in records
    )

    # Fetch each SEC filing once, then reconcile in a second pass. The watch is
    # sorted newest-first, so a one-pass implementation cannot safely use earlier
    # registration statements that appear later in the payload.
    evidence: dict[int, set[str]] = {}
    failed: set[int] = set()
    for record in records:
        try:
            evidence[id(record)] = extract_current_listing_tickers(fetch_text(record))
        except Exception as error:
            failed.add(id(record))
            label = record.get("company") or record.get("id") or "<unknown>"
            print(
                f"[ticker_listing_reconciler] Warning: could not inspect {label}: "
                f"{error}"
            )

    updated = 0
    conflicts = 0
    for record in records:
        current = str(record.get("ticker") or "").strip().upper()
        label = record.get("company") or record.get("id") or "<unknown>"
        key = _record_key(record)
        trusted_exact = str(verified_lineage.get(key) or "").strip().upper()

        if id(record) in failed:
            # A duplicate queue fetch may fail after the exact same accession was
            # already SEC-verified in the watch during this process. That exact
            # evidence is safe to retain; otherwise fail closed.
            authoritative = trusted_exact
            if authoritative:
                if authoritative != current:
                    record["ticker"] = authoritative
                    updated += 1
                print(
                    f"[ticker_listing_reconciler] {label}: retained SEC-verified "
                    f"watch ticker {authoritative} for exact accession"
                )
            elif current:
                record["ticker"] = ""
                updated += 1
                print(
                    f"[ticker_listing_reconciler] {label}: clearing unverified "
                    f"ticker {current} after filing inspection failure"
                )
            continue

        tickers = evidence.get(id(record), set())
        if len(tickers) > 1:
            conflicts += 1
            if current:
                record["ticker"] = ""
                updated += 1
            print(
                f"[ticker_listing_reconciler] {label}: conflicting current-listing "
                f"symbols {sorted(tickers)}; clearing ticker"
            )
            continue

        if len(tickers) == 1:
            authoritative = next(iter(tickers))
            if authoritative != current:
                record["ticker"] = authoritative
                updated += 1
                print(
                    f"[ticker_listing_reconciler] {label}: reconciled ticker "
                    f"{current or '<blank>'} -> {authoritative} from explicit SEC listing language"
                )
            continue

        # The current amendment was inspected successfully but does not repeat a
        # listing symbol. First accept exact-record evidence established by the
        # already-reconciled watch (used for the sibling public queue).
        if trusted_exact:
            if trusted_exact != current:
                record["ticker"] = trusted_exact
                updated += 1
            print(
                f"[ticker_listing_reconciler] {label}: preserved exact-accession "
                f"SEC-verified ticker {trusted_exact} from S-1 watch"
            )
            continue

        cik = _normalized_cik(record)
        filed = _filed(record)
        current_file_number = str(
            record.get(_REGISTRATION_FILE_NUMBER_KEY) or ""
        ).strip()

        if strict_registration_lineage and not current_file_number:
            # Production reconciliation explicitly requested SEC file-number
            # lineage but could not prove the current registration identity. Do
            # not fall back to same-CIK inheritance across an evidence gap.
            if current:
                record["ticker"] = ""
                updated += 1
            print(
                f"[ticker_listing_reconciler] {label}: SEC registration file-number "
                f"lineage unavailable; refusing earlier ticker carry-forward"
            )
            continue

        same_day = [
            other
            for other in records
            if other is not record
            and cik
            and _normalized_cik(other) == cik
            and filed
            and _filed(other) == filed
            and (
                not strict_registration_lineage
                or str(other.get(_REGISTRATION_FILE_NUMBER_KEY) or "").strip()
                == current_file_number
            )
        ]
        if same_day:
            # SEC filing dates do not establish ordering among same-day S-1/S-1A
            # accessions in the same registration statement. If this filing omits
            # the symbol, do not carry a symbol through that unordered event.
            if current:
                record["ticker"] = ""
                updated += 1
            print(
                f"[ticker_listing_reconciler] {label}: same-day S-1 registration "
                f"lineage cannot be ordered; refusing earlier ticker carry-forward"
            )
            continue

        prior = [
            other
            for other in records
            if other is not record
            and cik
            and _normalized_cik(other) == cik
            and filed
            and _filed(other)
            and _filed(other) < filed
            and (
                not strict_registration_lineage
                or str(other.get(_REGISTRATION_FILE_NUMBER_KEY) or "").strip()
                == current_file_number
            )
        ]

        # If any strictly earlier filing in the proven registration lineage could
        # not be inspected, do not infer through that gap. A missing amendment
        # could have changed the proposed symbol.
        prior_failed = any(id(other) in failed for other in prior)
        prior_conflict = any(len(evidence.get(id(other), set())) > 1 for other in prior)
        prior_tickers = {
            ticker
            for other in prior
            for ticker in evidence.get(id(other), set())
            if len(evidence.get(id(other), set())) == 1
        }

        if not prior_failed and not prior_conflict and len(prior_tickers) == 1:
            authoritative = next(iter(prior_tickers))
            if authoritative != current:
                record["ticker"] = authoritative
                updated += 1
            print(
                f"[ticker_listing_reconciler] {label}: carried forward ticker "
                f"{authoritative} from unambiguous earlier SEC registration lineage"
            )
            continue

        if len(prior_tickers) > 1 or prior_conflict:
            conflicts += 1
            print(
                f"[ticker_listing_reconciler] {label}: conflicting earlier S-1 "
                f"ticker lineage {sorted(prior_tickers)}; clearing ticker"
            )

        if current:
            record["ticker"] = ""
            updated += 1
            print(
                f"[ticker_listing_reconciler] {label}: no explicit current-listing "
                f"symbol or unambiguous SEC registration-lineage symbol found; "
                f"clearing unverified ticker {current}"
            )

    return updated, conflicts


def reconcile_file(
    path: Path,
    *,
    sync_csv: bool = False,
    verified_lineage: dict[tuple[str, str], str] | None = None,
) -> tuple[int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = [
        record
        for record in payload.get("filings", [])
        if isinstance(record, dict)
        and str(record.get("form") or "").strip().upper() in {"S-1", "S-1/A"}
    ]
    registration_lineage_map = _registration_file_numbers(records)
    for record in records:
        record[_REGISTRATION_FILE_NUMBER_KEY] = registration_lineage_map.get(
            _record_key(record), ""
        )

    try:
        updated, conflicts = reconcile_payload(
            payload, verified_lineage=verified_lineage
        )
    finally:
        # File-number lineage is a release-gate implementation detail, not part
        # of the public feed schema. Never persist it to JSON or CSV.
        for record in records:
            record.pop(_REGISTRATION_FILE_NUMBER_KEY, None)

    if updated:
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if sync_csv:
            dashboard_export.write_dashboard_csv(payload.get("filings", []), path)
    print(
        f"[ticker_listing_reconciler] inspected {len(payload.get('filings', []))} filing(s); "
        f"updated={updated}, conflicts={conflicts}"
    )
    return updated, conflicts


def main(argv=None) -> int:
    argv = list(argv or sys.argv[1:])
    path = Path(argv[0]) if argv else Path("../docs/data/s1_watch.json")
    reconcile_file(path)

    # s1_monitor.py writes both the dedicated watch and the Research Monitor queue
    # before this release gate runs. Reconcile the watch first, then let the queue
    # reuse only ticker evidence from the exact same CIK+accession. This keeps the
    # public surfaces consistent without falling back to ticker-only assumptions.
    if path.name == "s1_watch.json":
        queue_path = path.with_name("filings.json")
        if queue_path.exists():
            watch_payload = json.loads(path.read_text(encoding="utf-8"))
            verified_lineage = _verified_watch_tickers(watch_payload)
            reconcile_file(
                queue_path,
                sync_csv=True,
                verified_lineage=verified_lineage,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

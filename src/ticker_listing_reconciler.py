"""Reconcile pre-pricing S-1 tickers from explicit current listing language.

SEC submissions metadata can retain a stale historical ticker for a returning
issuer. For the pre-pricing watch, prefer the issuer's current S-1/S-1A
statement that it has applied, intends, or expects to list the offered shares
under a specific symbol. Conflicting current-listing statements fail closed.
"""

import json
import re
import sys
from pathlib import Path

import filing_parser


_CURRENT_LISTING_PATTERNS = [
    r"\bwe\s+(?:have\s+|has\s+)?applied\s+to\s+list\b.{0,600}?"
    r"\bunder\s+(?:the\s+)?(?:ticker\s+|trading\s+)?symbol\s*[\"'“‘]?([A-Z][A-Z0-9]{0,5})[\"'”’]?",
    r"\bapplication\s+(?:has\s+been|is)\s+(?:made|submitted)\s+(?:to|for)\s+(?:list|listing)\b.{0,600}?"
    r"\bunder\s+(?:the\s+)?(?:ticker\s+|trading\s+)?symbol\s*[\"'“‘]?([A-Z][A-Z0-9]{0,5})[\"'”’]?",
    r"\bwe\s+(?:intend|expect|plan)\s+to\s+(?:list|trade)\b.{0,600}?"
    r"\bunder\s+(?:the\s+)?(?:ticker\s+|trading\s+)?symbol\s*[\"'“‘]?([A-Z][A-Z0-9]{0,5})[\"'”’]?",
    r"\b(?:our\s+common\s+stock|the\s+common\s+stock|our\s+shares|the\s+shares)\s+"
    r"(?:has|have)\s+been\s+(?:approved|authorized)\s+for\s+listing\b.{0,600}?"
    r"\bunder\s+(?:the\s+)?(?:ticker\s+|trading\s+)?symbol\s*[\"'“‘]?([A-Z][A-Z0-9]{0,5})[\"'”’]?",
]


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
    return soup.get_text(" ", strip=True)[:100000]


def reconcile_payload(payload: dict, fetch_text=_fetch_filing_text) -> tuple[int, int]:
    """Reconcile S-1 watch tickers in place; return (updated, conflicts)."""
    updated = 0
    conflicts = 0
    for record in payload.get("filings", []):
        if not isinstance(record, dict):
            continue
        if str(record.get("form") or "").strip().upper() not in {"S-1", "S-1/A"}:
            continue
        if not str(record.get("sec_url") or "").strip():
            continue

        try:
            text = fetch_text(record)
        except Exception as error:
            print(
                f"[ticker_listing_reconciler] Warning: could not inspect "
                f"{record.get('company') or record.get('id')}: {error}"
            )
            continue

        tickers = extract_current_listing_tickers(text)
        current = str(record.get("ticker") or "").strip().upper()
        label = record.get("company") or record.get("id") or "<unknown>"

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
        if len(tickers) != 1:
            continue

        authoritative = next(iter(tickers))
        if authoritative != current:
            record["ticker"] = authoritative
            updated += 1
            print(
                f"[ticker_listing_reconciler] {label}: reconciled ticker "
                f"{current or '<blank>'} -> {authoritative} from explicit SEC listing language"
            )

    return updated, conflicts


def reconcile_file(path: Path) -> tuple[int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    updated, conflicts = reconcile_payload(payload)
    if updated:
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(
        f"[ticker_listing_reconciler] inspected {len(payload.get('filings', []))} filing(s); "
        f"updated={updated}, conflicts={conflicts}"
    )
    return updated, conflicts


def main(argv=None) -> int:
    argv = list(argv or sys.argv[1:])
    path = Path(argv[0]) if argv else Path("../docs/data/s1_watch.json")
    reconcile_file(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

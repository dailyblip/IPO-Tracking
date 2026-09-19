"""Recover SEC-confirmed ticker symbols for priced 424B4 rows that are blank.

Lifecycle reconciliation intentionally fails closed when the final prospectus cannot
be fetched to affirm an already-stored ticker. A transient SEC fetch failure can
therefore leave a valid priced IPO with a blank ticker. This bounded post-lifecycle
repair retries the exact final filing and restores a symbol only when that same
424B4 cover page explicitly discloses an exchange listing/trading symbol. It never
restores Current Price or any quote-derived value.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import dashboard_export
import edgar_client
import filing_parser

MAX_FETCH_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 0.5

_LISTING_PATTERNS = (
    r"\b(?:list|listed|listing|trade|traded|trading|quote|quoted|quotation)\b.{0,300}?"
    r"\bunder\s+(?:the\s+)?(?:ticker\s+|trading\s+)?symbol\s*[\"“]?([A-Z]{1,6})[\"”]?",
    r"\bunder\s+(?:the\s+)?ticker\s+symbol\s*[\"“]?([A-Z]{1,6})[\"”]?",
    r"\btrading\s+symbol\s*[:\-]?\s*[\"“]?([A-Z]{1,6})[\"”]?",
)
_MARKET_VALUE_SIGNAL_MARKERS = ("currently valued", "current market value")
_MARKET_DERIVED_PERSON_FIELDS = (
    "cash_value",
    "liquid_value",
    "locked_value",
    "valuation_as_of",
)


def _canonical_cik(value) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits or len(digits) > 10:
        return ""
    return digits.zfill(10)


def _canonical_accession(value) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 18:
        return ""
    return f"{digits[:10]}-{digits[10:12]}-{digits[12:]}"


def _record_accession(record: dict) -> str:
    accession = _canonical_accession(record.get("accession_no"))
    record_id = _canonical_accession(record.get("id"))
    if accession and record_id and accession != record_id:
        return ""
    return accession or record_id


def _is_blank_priced_final(record: dict) -> bool:
    return (
        str(record.get("form") or "").strip().upper() == "424B4"
        and str(record.get("stage") or "").strip().casefold() == "priced"
        and not str(record.get("ticker") or "").strip()
        and record.get("offering_price") not in (None, "")
    )


def _extract_explicit_listing_ticker(soup) -> str:
    """Return one unambiguous final-cover listing symbol; reject generic mentions."""
    cover_text = soup.get_text(" ", strip=True)[:100000]
    tickers = set()
    for pattern in _LISTING_PATTERNS:
        for match in re.finditer(pattern, cover_text, re.IGNORECASE):
            ticker = match.group(1)
            if ticker == ticker.upper():
                tickers.add(ticker)
    if len(tickers) != 1:
        return ""
    return next(iter(tickers))


def _clear_quote_derived_fields(filing: dict) -> None:
    """Remove market values that cannot survive an identity-repair handoff."""
    filing.pop("current_price", None)
    filing.pop("price_updated", None)

    people = filing.get("people")
    if isinstance(people, list):
        for person in people:
            if not isinstance(person, dict):
                continue
            for field in _MARKET_DERIVED_PERSON_FIELDS:
                person.pop(field, None)

    signals = filing.get("signals")
    if isinstance(signals, list):
        filing["signals"] = [
            signal
            for signal in signals
            if not (
                isinstance(signal, str)
                and any(
                    marker in signal.casefold()
                    for marker in _MARKET_VALUE_SIGNAL_MARKERS
                )
            )
        ]


def _load_exact_final_soup(record: dict):
    cik = _canonical_cik(record.get("cik"))
    accession = _record_accession(record)
    if not cik or not accession:
        raise filing_parser.FilingParserError(
            "priced 424B4 is missing an exact SEC CIK/accession identity"
        )
    index_url = edgar_client.build_filing_index_url(cik, accession)
    document_url = filing_parser.find_primary_document_url(
        index_url,
        expected_form_types=["424B4"],
    )
    return filing_parser.fetch_document(document_url)


def _load_with_retries(
    record: dict,
    soup_loader,
    attempts: int,
    retry_delay_seconds: float,
):
    attempts = max(1, int(attempts))
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return soup_loader(record)
        except Exception as error:  # SEC/network/parser failures are fail-closed here.
            last_error = error
            if attempt < attempts and retry_delay_seconds > 0:
                time.sleep(retry_delay_seconds)
    company = str(record.get("company") or "Unknown issuer").strip()
    print(
        "Final ticker recovery: SEC final-document review unavailable for "
        f"{company} after {attempts} attempt(s); ticker remains blank: {last_error}"
    )
    return None


def recover_payload(
    payload: dict,
    soup_loader=None,
    attempts: int = MAX_FETCH_ATTEMPTS,
    retry_delay_seconds: float = RETRY_DELAY_SECONDS,
) -> tuple[dict, int]:
    """Restore only tickers explicitly confirmed by the row's exact final 424B4."""
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("Public feed must contain a filings list")

    soup_loader = soup_loader or _load_exact_final_soup
    recovered = 0
    for filing in filings:
        if not isinstance(filing, dict) or not _is_blank_priced_final(filing):
            continue

        # Conflicting or incomplete filing identity is never a basis for recovery.
        if not _canonical_cik(filing.get("cik")) or not _record_accession(filing):
            continue

        soup = _load_with_retries(
            filing,
            soup_loader=soup_loader,
            attempts=attempts,
            retry_delay_seconds=retry_delay_seconds,
        )
        if soup is None:
            continue

        ticker = _extract_explicit_listing_ticker(soup)
        if not ticker:
            continue

        filing["ticker"] = ticker
        # Ticker recovery is SEC identity repair only. Never resurrect or preserve
        # market-derived economics that were calculated while ticker identity was
        # unresolved. The normal priced-IPO quote refresh may repopulate them later
        # from a verified final lifecycle state.
        _clear_quote_derived_fields(filing)
        recovered += 1
        print(
            "Final ticker recovery: restored SEC-confirmed ticker "
            f"{ticker} for {filing.get('company') or 'Unknown issuer'}"
        )

    if recovered:
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    return payload, recovered


def recover_feed(
    path: Path,
    attempts: int = MAX_FETCH_ATTEMPTS,
    retry_delay_seconds: float = RETRY_DELAY_SECONDS,
) -> int:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload, recovered = recover_payload(
        payload,
        attempts=attempts,
        retry_delay_seconds=retry_delay_seconds,
    )
    if recovered:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        dashboard_export.write_dashboard_csv(payload.get("filings", []), path)
    return recovered


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Recover a blank priced-IPO ticker only when the exact final 424B4 "
            "explicitly confirms the exchange listing/trading symbol."
        )
    )
    parser.add_argument("feed", help="Path to docs/data/filings.json")
    args = parser.parse_args(argv)
    recovered = recover_feed(Path(args.feed))
    print(f"Recovered {recovered} SEC-confirmed final ticker(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

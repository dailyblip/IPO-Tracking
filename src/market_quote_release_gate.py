"""Release-safe market quote identity gate.

Current Price is secondary data. If the market-data identity provider is unavailable
after its bounded retries, or cannot finish identity review inside the release time
budget, publish no unverified market quote rather than blocking otherwise
authoritative SEC IPO data. Deterministic lifecycle or issuer/ticker identity defects
remain release-blocking/sanitized by market_quote_identity.

Quote freshness is revalidated here against the final repaired lifecycle state before
provider/SEC identity review. This prevents a quote that was valid before lifecycle or
pricing reconciliation from surviving after authoritative filing/pricing dates advance.

Before quote review, blank priced-IPO tickers receive one bounded recovery pass against
the exact final 424B4. This is SEC identity repair only: a symbol is restored only when
the final prospectus explicitly confirms it, and no Current Price is restored with it.

Every quote that survives the market profile check must also receive a second-factor
CIK/ticker check against the authoritative SEC issuer profile. Provider identity is
necessary but not sufficient: if SEC identity verification is unavailable or
misconfigured, publish no unverified market quote rather than risk attaching a stale
or reused ticker to the wrong historical issuer.

For quotes stamped on the same Eastern calendar day as the final 424B4, calendar-date
freshness alone cannot prove that public trading data followed SEC acceptance of the
final prospectus. Those same-day quotes therefore require exact accession-level SEC
acceptance chronology and must be strictly later than the 424B4 acceptance timestamp.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import dashboard_export
import final_ticker_reconciler as final_ticker
import market_price_freshness_gate as freshness
import market_quote_identity as identity

IDENTITY_AUDIT_TIME_BUDGET_SECONDS = 180
_SEC_FILING_TIMEZONE = ZoneInfo("America/New_York")


def _write_payload(path: Path, payload: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)
    dashboard_export.write_dashboard_csv(payload.get("filings", []), path)


def _revalidate_quote_freshness(path: Path) -> int:
    """Recheck quotes against the final repaired lifecycle state before release."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload, stale = freshness.sanitize_payload(payload)
    if stale:
        _write_payload(path, payload)
        for item in stale:
            print(
                "Market quote release gate: cleared Current Price for "
                f"{item['company']} ({item['ticker'] or 'no ticker'}) after "
                "post-lifecycle freshness recheck"
            )
    return len(stale)


def _clear_unverified_quotes(payload: dict) -> int:
    cleared = 0
    for filing in payload.get("filings", []):
        if not isinstance(filing, dict) or filing.get("current_price") in (None, ""):
            continue
        identity._strip_quote_derived_fields(filing)
        cleared += 1
    return cleared


def _normalize_sec_tickers(value):
    """Return normalized SEC tickers only when submissions metadata is well formed."""
    if not isinstance(value, list):
        return None

    tickers = set()
    for item in value:
        if not isinstance(item, str):
            return None
        ticker = item.strip().upper()
        if not ticker:
            return None
        tickers.add(ticker)
    return tickers


def _canonical_accession(value) -> str:
    """Normalize an SEC accession for exact identity comparison only."""
    return "".join(character for character in str(value or "") if character.isdigit())


def _sec_acceptance_timestamp(value):
    """Parse SEC acceptance metadata as an aware instant.

    EDGAR header-style 14-digit acceptance times are Eastern Time. Submissions JSON
    can also expose ISO timestamps; explicit offsets are retained, while an offsetless
    ISO value is interpreted on the same SEC Eastern calendar used by the release
    freshness gate.
    """
    raw = str(value or "").strip()
    if not raw:
        return None

    if len(raw) == 14 and raw.isdigit():
        try:
            return datetime.strptime(raw, "%Y%m%d%H%M%S").replace(
                tzinfo=_SEC_FILING_TIMEZONE
            )
        except ValueError:
            return None

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=_SEC_FILING_TIMEZONE)
    return parsed


def _same_day_quote_chronology_reason(filing: dict, sec_profile: dict) -> str | None:
    """Return a fail-closed reason when same-day quote order is not authoritative.

    The ordinary freshness gate already proves that a quote is not on an Eastern
    calendar date before the final 424B4. On a strictly later date, no intraday SEC
    ordering check is necessary. When both occur on the same date, however, the exact
    final accession must be present in SEC submissions metadata and the provider quote
    must be strictly later than that filing's acceptance time.
    """
    quote_timestamp = freshness._timestamp(filing.get("price_updated"))
    final_filing_date = freshness._date(filing.get("filed"))
    if quote_timestamp is None or final_filing_date is None:
        return "quote chronology lacks a canonical timestamp or final filing date"

    quote_date_eastern = quote_timestamp.astimezone(_SEC_FILING_TIMEZONE).date()
    if quote_date_eastern > final_filing_date:
        return None
    if quote_date_eastern < final_filing_date:
        return "quote timestamp predates the final 424B4 filing date"

    final_accession = _canonical_accession(
        filing.get("accession_no") or filing.get("id")
    )
    if not final_accession:
        return "same-day quote lacks exact final accession provenance"

    filings = (sec_profile or {}).get("filings")
    recent = filings.get("recent") if isinstance(filings, dict) else None
    if not isinstance(recent, dict):
        return "SEC submissions lacks recent filing chronology for same-day quote"

    fields = ("accessionNumber", "form", "filingDate", "acceptanceDateTime")
    columns = [recent.get(field) for field in fields]
    if any(not isinstance(column, list) for column in columns):
        return "SEC submissions same-day filing chronology is malformed"
    lengths = {len(column) for column in columns}
    if len(lengths) != 1:
        return "SEC submissions same-day filing chronology is misaligned"

    matches = []
    for accession, form, filing_date, acceptance in zip(*columns):
        if (
            _canonical_accession(accession) == final_accession
            and str(form or "").strip().upper() == "424B4"
            and str(filing_date or "").strip() == final_filing_date.isoformat()
        ):
            matches.append(acceptance)

    if len(matches) != 1:
        return "SEC submissions cannot uniquely confirm the same-day final 424B4"

    acceptance_timestamp = _sec_acceptance_timestamp(matches[0])
    if acceptance_timestamp is None:
        return "SEC submissions lacks a valid final 424B4 acceptance time"
    if acceptance_timestamp.astimezone(_SEC_FILING_TIMEZONE).date() != final_filing_date:
        return "SEC final 424B4 acceptance time conflicts with the filing date"
    if quote_timestamp <= acceptance_timestamp:
        return "same-day quote does not postdate final 424B4 SEC acceptance"
    return None


def _sec_quote_identity_crosscheck(path: Path) -> tuple[int, int]:
    """Cross-check surviving quote tickers and chronology against the filing CIK.

    Finnhub already establishes provider ticker/name identity. This second factor is
    intentionally narrower: SEC submissions must agree that the filing CIK currently
    carries the same ticker. We do not require the SEC display name to equal the
    historical prospectus name because legitimate post-IPO issuer renames are
    expected. Same-day quotes additionally require exact final-accession acceptance
    chronology so a pre-424B4 quote cannot survive merely because it shares the same
    Eastern calendar date.
    """
    user_agent = str(os.environ.get("SEC_EDGAR_USER_AGENT") or "").strip()
    if not user_agent:
        raise identity.QuoteProviderError(
            "SEC_EDGAR_USER_AGENT is required for authoritative SEC quote-identity cross-check"
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    lookup_sec_profile = identity._paced_sec_lookup(user_agent)
    sec_profiles: dict[str, dict] = {}
    audited = 0
    sanitized = []

    for filing in payload.get("filings", []):
        if not isinstance(filing, dict) or filing.get("current_price") in (None, ""):
            continue

        company, ticker = identity._validate_lifecycle(filing)
        cik = identity._normalize_cik(filing.get("cik"))
        if not cik:
            identity._strip_quote_derived_fields(filing)
            sanitized.append(
                (company or "Unknown issuer", ticker or "no ticker", "missing filing CIK")
            )
            continue

        if cik not in sec_profiles:
            sec_profiles[cik] = lookup_sec_profile(cik)
        sec_profile = sec_profiles[cik]

        sec_cik = identity._normalize_cik((sec_profile or {}).get("cik"))
        sec_tickers = _normalize_sec_tickers((sec_profile or {}).get("tickers"))

        reason = None
        if not sec_cik:
            reason = "SEC submissions profile is missing a confirmable CIK"
        elif sec_cik != cik:
            reason = f"SEC submissions CIK {sec_cik} does not match filing CIK {cik}"
        elif sec_tickers is None:
            reason = "SEC submissions ticker metadata is malformed"
        elif ticker not in sec_tickers:
            reason = "SEC submissions profile does not confirm the filing ticker"
        else:
            reason = _same_day_quote_chronology_reason(filing, sec_profile)

        if reason:
            identity._strip_quote_derived_fields(filing)
            sanitized.append((company, ticker, reason))
            continue
        audited += 1

    if sanitized:
        _write_payload(path, payload)
        for company, ticker, reason in sanitized:
            print(
                "SEC quote identity cross-check: cleared Current Price for "
                f"{company} ({ticker}): {reason}"
            )

    return audited, len(sanitized)


def _run_identity_gates(path: Path, api_key: str) -> tuple[int, int]:
    audited, sanitized = identity.sanitize_feed(path, api_key=api_key)
    sec_audited, sec_sanitized = _sec_quote_identity_crosscheck(path)
    return sec_audited, sanitized + sec_sanitized


def _sanitize_with_time_budget(
    path: Path,
    api_key: str,
    time_budget_seconds: float | None,
) -> tuple[int, int]:
    """Bound secondary quote verification so it cannot starve release publication."""
    if (
        time_budget_seconds is None
        or time_budget_seconds <= 0
        or not hasattr(signal, "SIGALRM")
        or not hasattr(signal, "setitimer")
    ):
        return _run_identity_gates(path, api_key)

    previous_handler = signal.getsignal(signal.SIGALRM)

    def _expire(signum, frame):
        raise identity.QuoteProviderError(
            "market quote identity review exceeded the "
            f"{time_budget_seconds:g}-second release time budget"
        )

    signal.signal(signal.SIGALRM, _expire)
    signal.setitimer(signal.ITIMER_REAL, float(time_budget_seconds))
    try:
        return _run_identity_gates(path, api_key)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def enforce_release_gate(
    path: Path,
    api_key: str | None = None,
    time_budget_seconds: float | None = IDENTITY_AUDIT_TIME_BUDGET_SECONDS,
) -> tuple[int, int]:
    """Recover final SEC ticker identity, then revalidate quote freshness/identity."""
    path = Path(path)
    api_key = api_key or os.environ.get("MARKET_DATA_API_KEY")
    if not api_key:
        raise identity.QuoteProviderError(
            "MARKET_DATA_API_KEY is required to verify populated Current Price values"
        )

    # Lifecycle remains fail-closed when its one final-document fetch is unavailable.
    # Give blank priced tickers a bounded second chance against the exact same 424B4.
    # Recovery never restores Current Price, which remains subject to the independent
    # freshness, provider-identity, and SEC CIK/ticker gates below.
    final_ticker.recover_feed(path)
    _revalidate_quote_freshness(path)

    try:
        return _sanitize_with_time_budget(path, api_key, time_budget_seconds)
    except identity.QuoteProviderError as exc:
        payload = json.loads(path.read_text(encoding="utf-8"))
        cleared = _clear_unverified_quotes(payload)
        if cleared:
            _write_payload(path, payload)
        print(
            "Market quote identity provider unavailable or over release time budget; "
            f"cleared {cleared} unverified Current Price value(s) and preserved "
            f"authoritative IPO data: {exc}"
        )
        return 0, cleared


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Revalidate market-quote freshness and issuer identity; if the secondary "
            "identity provider is unavailable or exceeds its release time budget, "
            "clear unverified quote-derived fields before release."
        )
    )
    parser.add_argument("feed", help="Path to docs/data/filings.json")
    args = parser.parse_args(argv)
    try:
        enforce_release_gate(Path(args.feed))
    except (OSError, json.JSONDecodeError, identity.QuoteIdentityError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

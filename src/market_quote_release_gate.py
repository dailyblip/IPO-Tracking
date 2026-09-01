"""Release-safe market quote identity gate.

Current Price is secondary data. If the market-data identity provider is unavailable
after its bounded retries, or cannot finish identity review inside the release time
budget, publish no unverified market quote rather than blocking otherwise
authoritative SEC IPO data. Deterministic lifecycle or issuer/ticker identity defects
remain release-blocking/sanitized by market_quote_identity.

When SEC submissions access is configured, every quote that survives the market
profile check receives a second-factor CIK/ticker check against the authoritative
SEC issuer profile. This prevents a deceptively similar provider name from allowing
a stale or reused ticker to attach a live quote to the wrong historical issuer.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
from pathlib import Path

import dashboard_export
import market_quote_identity as identity

IDENTITY_AUDIT_TIME_BUDGET_SECONDS = 180


def _write_payload(path: Path, payload: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)
    dashboard_export.write_dashboard_csv(payload.get("filings", []), path)


def _clear_unverified_quotes(payload: dict) -> int:
    cleared = 0
    for filing in payload.get("filings", []):
        if not isinstance(filing, dict) or filing.get("current_price") in (None, ""):
            continue
        identity._strip_quote_derived_fields(filing)
        cleared += 1
    return cleared


def _sec_quote_identity_crosscheck(path: Path) -> tuple[int, int] | None:
    """Cross-check surviving quote tickers against the exact filing CIK at SEC.

    Finnhub already establishes provider ticker/name identity. This second factor is
    intentionally narrower: SEC submissions must agree that the filing CIK currently
    carries the same ticker. We do not require the SEC display name to equal the
    historical prospectus name because legitimate post-IPO issuer renames are
    expected.
    """
    user_agent = str(os.environ.get("SEC_EDGAR_USER_AGENT") or "").strip()
    if not user_agent:
        return None

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
        raw_tickers = (sec_profile or {}).get("tickers") or []
        if isinstance(raw_tickers, str):
            raw_tickers = [raw_tickers]
        sec_tickers = {
            str(item or "").strip().upper()
            for item in raw_tickers
            if str(item or "").strip()
        }

        reason = None
        if not sec_cik:
            reason = "SEC submissions profile is missing a confirmable CIK"
        elif sec_cik != cik:
            reason = f"SEC submissions CIK {sec_cik} does not match filing CIK {cik}"
        elif ticker not in sec_tickers:
            reason = "SEC submissions profile does not confirm the filing ticker"

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
    sec_result = _sec_quote_identity_crosscheck(path)
    if sec_result is None:
        return audited, sanitized
    sec_audited, sec_sanitized = sec_result
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
    """Run strict identity validation; blank all quotes on provider outage/budget."""
    path = Path(path)
    api_key = api_key or os.environ.get("MARKET_DATA_API_KEY")
    if not api_key:
        raise identity.QuoteProviderError(
            "MARKET_DATA_API_KEY is required to verify populated Current Price values"
        )

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
            "Verify market-quote issuer identity; if the secondary identity provider "
            "is unavailable or exceeds its release time budget, clear unverified "
            "quote-derived fields before release."
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

"""Fail closed when a market-data ticker resolves to the wrong issuer.

The Research Monitor treats Current Price as secondary data. SEC filings establish
IPO identity. Finnhub Company Profile 2 is the primary quote-identity check. When
that profile is incomplete for a newly listed issuer, SEC submissions metadata may
supply the missing issuer/ticker identity. A provider issuer-name change may also be
reconciled only when SEC submissions for the filing CIK confirms the same ticker and
current provider issuer name. Provider ticker conflicts are never overridden.
"""

import argparse
import json
import os
import re
import time
from pathlib import Path

import requests

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
SEC_SUBMISSIONS_BASE_URL = "https://data.sec.gov/submissions"
PROFILE_TIMEOUT_SECONDS = 10
PROFILE_MAX_RETRIES = 4
PROFILE_RETRY_BACKOFF_SECONDS = 5
PROFILE_MIN_INTERVAL_SECONDS = 1.1
SEC_TIMEOUT_SECONDS = 10
SEC_MAX_RETRIES = 4
SEC_RETRY_BACKOFF_SECONDS = 3
SEC_MIN_INTERVAL_SECONDS = 0.2

_CORPORATE_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "co", "company",
    "ltd", "limited", "plc", "llc", "lp",
}
_GENERIC_NAME_TOKENS = {
    "group", "holdings", "holding", "financial", "technology",
    "technologies", "solutions", "systems", "international", "global",
}
_MARKET_VALUE_SIGNAL_MARKERS = ("currently valued", "current market value")


class QuoteIdentityError(RuntimeError):
    """Raised when a populated market quote cannot be tied to the SEC issuer."""


class QuoteProviderError(QuoteIdentityError):
    """Raised when an identity provider cannot complete a lookup reliably."""


def _identity_tokens(name):
    raw_name = str(name or "").strip()
    # SEC issuer strings can carry a terminal incorporation marker such as /DE/.
    raw_name = re.sub(r"/[A-Z]{2}/\s*$", "", raw_name, flags=re.IGNORECASE)
    tokens = re.findall(r"[a-z0-9]+", raw_name.casefold())
    while tokens and tokens[-1] in _CORPORATE_SUFFIXES:
        tokens.pop()
    return tokens


def _company_names_match(expected_name, provider_name):
    """Conservatively compare SEC issuer and identity-provider company names."""
    expected = _identity_tokens(expected_name)
    provider = _identity_tokens(provider_name)
    if not expected or not provider:
        return False
    if expected == provider:
        return True

    expected_set = set(expected)
    provider_set = set(provider)
    common = expected_set & provider_set
    if not (common - _GENERIC_NAME_TOKENS):
        return False

    smaller, larger = (
        (expected_set, provider_set)
        if len(expected_set) <= len(provider_set)
        else (provider_set, expected_set)
    )
    if len(smaller) >= 2 and smaller <= larger:
        return True
    return len(common) / max(len(expected_set | provider_set), 1) >= 0.8


def _provider_identity_is_complete(ticker, company_name, profile):
    """Validate populated Finnhub identity fields and report completeness.

    Missing fields are not a collision because newly listed symbols can have a
    live quote before Company Profile 2 is fully indexed. This helper remains
    deliberately strict; _verify_identity may separately reconcile a name-only
    change using the filing CIK plus authoritative SEC submissions metadata.
    """
    provider_ticker = str((profile or {}).get("ticker") or "").strip().upper()
    provider_name = str((profile or {}).get("name") or "").strip()
    expected_ticker = str(ticker or "").strip().upper()

    if provider_ticker and provider_ticker != expected_ticker:
        raise QuoteIdentityError(
            f"{company_name}: market profile ticker {provider_ticker} does not match "
            f"SEC/filing ticker {expected_ticker or 'missing'}"
        )
    if provider_name and not _company_names_match(company_name, provider_name):
        raise QuoteIdentityError(
            f"{company_name} ({expected_ticker}): market profile resolves to "
            f"{provider_name!r}; refusing to publish a possibly collided quote"
        )
    return bool(provider_ticker and provider_name)


def _validate_profile(ticker, company_name, profile):
    """Strict Finnhub-only validation retained for tests and manual audits."""
    if _provider_identity_is_complete(ticker, company_name, profile):
        return True
    provider_ticker = str((profile or {}).get("ticker") or "").strip().upper()
    provider_name = str((profile or {}).get("name") or "").strip()
    expected_ticker = str(ticker or "").strip().upper()
    if not provider_ticker:
        raise QuoteIdentityError(
            f"{company_name}: market profile ticker missing does not match "
            f"SEC/filing ticker {expected_ticker or 'missing'}"
        )
    if not provider_name:
        raise QuoteIdentityError(
            f"{company_name} ({expected_ticker}): market profile is missing issuer name"
        )
    return True


def _normalize_cik(cik):
    digits = re.sub(r"\D", "", str(cik or ""))
    return digits.zfill(10) if digits else ""


def _validate_sec_identity(
    ticker, company_name, cik, sec_profile, corroborating_name=None
):
    """Validate issuer/ticker identity using authoritative SEC submissions data."""
    expected_ticker = str(ticker or "").strip().upper()
    expected_cik = _normalize_cik(cik)
    sec_name = str((sec_profile or {}).get("name") or "").strip()
    sec_cik = _normalize_cik((sec_profile or {}).get("cik"))
    raw_tickers = (sec_profile or {}).get("tickers") or []
    if isinstance(raw_tickers, str):
        raw_tickers = [raw_tickers]
    sec_tickers = {
        str(item or "").strip().upper()
        for item in raw_tickers
        if str(item or "").strip()
    }

    if not expected_cik:
        raise QuoteIdentityError(
            f"{company_name} ({expected_ticker or 'no ticker'}): "
            "SEC fallback requires a filing CIK"
        )
    if sec_cik and sec_cik != expected_cik:
        raise QuoteIdentityError(
            f"{company_name} ({expected_ticker}): SEC submissions CIK {sec_cik} "
            f"does not match filing CIK {expected_cik}"
        )
    if expected_ticker not in sec_tickers:
        raise QuoteIdentityError(
            f"{company_name} ({expected_ticker}): SEC submissions profile does not "
            "confirm the filing ticker"
        )

    expected_name = str(corroborating_name or company_name).strip()
    if not sec_name or not _company_names_match(expected_name, sec_name):
        match_target = (
            "current market-profile issuer" if corroborating_name else "filing issuer"
        )
        raise QuoteIdentityError(
            f"{company_name} ({expected_ticker}): SEC submissions issuer "
            f"{sec_name or 'missing'} does not match the {match_target}"
        )
    return True


def _retry_delay(response, attempt, default_backoff=PROFILE_RETRY_BACKOFF_SECONDS):
    raw = str((getattr(response, "headers", {}) or {}).get("Retry-After") or "").strip()
    try:
        return max(float(raw), 0.0)
    except (TypeError, ValueError):
        return default_backoff * attempt


def _fetch_profile(ticker, api_key):
    """Fetch one Finnhub profile with bounded retry for quota/server failures."""
    last_error = None
    for attempt in range(1, PROFILE_MAX_RETRIES + 1):
        try:
            response = requests.get(
                f"{FINNHUB_BASE_URL}/stock/profile2",
                params={"symbol": ticker, "token": api_key},
                timeout=PROFILE_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            last_error = exc
            if attempt < PROFILE_MAX_RETRIES:
                time.sleep(PROFILE_RETRY_BACKOFF_SECONDS * attempt)
                continue
            raise QuoteProviderError(
                f"Could not verify market-data identity for {ticker}: {exc}"
            ) from exc

        status = int(getattr(response, "status_code", 0) or 0)
        if status == 429 or 500 <= status < 600:
            last_error = RuntimeError(f"HTTP {status}")
            if attempt < PROFILE_MAX_RETRIES:
                time.sleep(max(_retry_delay(response, attempt), PROFILE_MIN_INTERVAL_SECONDS))
                continue
            raise QuoteProviderError(
                f"Could not verify market-data identity for {ticker}: provider returned "
                f"HTTP {status} after {PROFILE_MAX_RETRIES} attempts"
            )
        try:
            response.raise_for_status()
            profile = response.json()
        except requests.RequestException as exc:
            raise QuoteProviderError(
                f"Could not verify market-data identity for {ticker}: {exc}"
            ) from exc
        except ValueError as exc:
            raise QuoteProviderError(
                f"Could not verify market-data identity for {ticker}: invalid JSON response"
            ) from exc
        if not isinstance(profile, dict):
            raise QuoteProviderError(
                f"Could not verify market-data identity for {ticker}: invalid company profile"
            )
        return profile
    raise QuoteProviderError(
        f"Could not verify market-data identity for {ticker}: {last_error}"
    )


def _fetch_sec_profile(cik, user_agent):
    """Fetch SEC submissions metadata for one issuer CIK."""
    normalized_cik = _normalize_cik(cik)
    if not normalized_cik:
        raise QuoteIdentityError("SEC fallback cannot run without a valid CIK")
    if not str(user_agent or "").strip():
        raise QuoteProviderError(
            "SEC_EDGAR_USER_AGENT is required for SEC market-identity fallback"
        )

    url = f"{SEC_SUBMISSIONS_BASE_URL}/CIK{normalized_cik}.json"
    last_error = None
    for attempt in range(1, SEC_MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                headers={
                    "User-Agent": str(user_agent).strip(),
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip, deflate",
                },
                timeout=SEC_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            last_error = exc
            if attempt < SEC_MAX_RETRIES:
                time.sleep(SEC_RETRY_BACKOFF_SECONDS * attempt)
                continue
            raise QuoteProviderError(
                f"Could not verify SEC issuer identity for CIK {normalized_cik}: {exc}"
            ) from exc

        status = int(getattr(response, "status_code", 0) or 0)
        if status == 404:
            raise QuoteIdentityError(
                f"SEC submissions profile unavailable for CIK {normalized_cik}"
            )
        if status == 429 or 500 <= status < 600:
            last_error = RuntimeError(f"HTTP {status}")
            if attempt < SEC_MAX_RETRIES:
                time.sleep(max(
                    _retry_delay(response, attempt, SEC_RETRY_BACKOFF_SECONDS),
                    SEC_MIN_INTERVAL_SECONDS,
                ))
                continue
            raise QuoteProviderError(
                f"Could not verify SEC issuer identity for CIK {normalized_cik}: "
                f"SEC returned HTTP {status} after {SEC_MAX_RETRIES} attempts"
            )
        try:
            response.raise_for_status()
            profile = response.json()
        except requests.RequestException as exc:
            raise QuoteProviderError(
                f"Could not verify SEC issuer identity for CIK {normalized_cik}: {exc}"
            ) from exc
        except ValueError as exc:
            raise QuoteProviderError(
                f"Could not verify SEC issuer identity for CIK {normalized_cik}: "
                "invalid JSON response"
            ) from exc
        if not isinstance(profile, dict):
            raise QuoteProviderError(
                f"Could not verify SEC issuer identity for CIK {normalized_cik}: "
                "invalid submissions profile"
            )
        return profile
    raise QuoteProviderError(
        f"Could not verify SEC issuer identity for CIK {normalized_cik}: {last_error}"
    )


def _paced_profile_lookup(api_key):
    last_started = [None]
    def lookup(ticker):
        now = time.monotonic()
        if last_started[0] is not None:
            elapsed = now - last_started[0]
            if elapsed < PROFILE_MIN_INTERVAL_SECONDS:
                time.sleep(PROFILE_MIN_INTERVAL_SECONDS - elapsed)
        last_started[0] = time.monotonic()
        return _fetch_profile(ticker, api_key)
    return lookup


def _paced_sec_lookup(user_agent):
    last_started = [None]
    def lookup(cik):
        now = time.monotonic()
        if last_started[0] is not None:
            elapsed = now - last_started[0]
            if elapsed < SEC_MIN_INTERVAL_SECONDS:
                time.sleep(SEC_MIN_INTERVAL_SECONDS - elapsed)
        last_started[0] = time.monotonic()
        return _fetch_sec_profile(cik, user_agent)
    return lookup


def _strip_quote_derived_fields(filing):
    """Remove a quote and values calculated from that quote."""
    touched = False
    for field in ("current_price", "price_updated"):
        if field in filing:
            filing.pop(field, None)
            touched = True
    for person in filing.get("people", []):
        if not isinstance(person, dict):
            continue
        for field in ("cash_value", "liquid_value", "locked_value", "valuation_as_of"):
            if field in person:
                person.pop(field, None)
                touched = True
    signals = filing.get("signals")
    if isinstance(signals, list):
        kept = []
        for signal in signals:
            text = str(signal or "").casefold()
            if any(marker in text for marker in _MARKET_VALUE_SIGNAL_MARKERS):
                touched = True
                continue
            kept.append(signal)
        if len(kept) != len(signals):
            filing["signals"] = kept
    return touched


def _verify_identity(filing, provider_profile, lookup_sec_profile=None, sec_profiles=None):
    """Verify quote identity with fail-closed SEC corroboration for issuer renames."""
    company = str(filing.get("company") or "").strip()
    ticker = str(filing.get("ticker") or "").strip().upper()
    provider_ticker = str((provider_profile or {}).get("ticker") or "").strip().upper()
    provider_name = str((provider_profile or {}).get("name") or "").strip()
    corroborating_name = None

    try:
        if _provider_identity_is_complete(ticker, company, provider_profile):
            return "finnhub"
    except QuoteIdentityError:
        # A ticker disagreement is an explicit collision and can never be
        # overridden. A name-only disagreement may reflect a legitimate issuer
        # rename, but only when the provider confirms the filing ticker and the
        # exact filing CIK can corroborate that current issuer name via SEC.
        if provider_ticker != ticker or not provider_name or lookup_sec_profile is None:
            raise
        corroborating_name = provider_name
    else:
        if lookup_sec_profile is None:
            _validate_profile(ticker, company, provider_profile)

    cik = _normalize_cik(filing.get("cik"))
    if not cik:
        context = (
            "issuer-name reconciliation" if corroborating_name else "SEC fallback"
        )
        raise QuoteIdentityError(
            f"{company} ({ticker}): {context} requires a filing CIK"
        )
    sec_profiles = sec_profiles if sec_profiles is not None else {}
    if cik not in sec_profiles:
        sec_profiles[cik] = lookup_sec_profile(cik)
    _validate_sec_identity(
        ticker,
        company,
        cik,
        sec_profiles[cik],
        corroborating_name=corroborating_name,
    )
    return "sec_submissions"


def _validate_lifecycle(filing):
    company = str(filing.get("company") or "").strip()
    ticker = str(filing.get("ticker") or "").strip().upper()
    form = str(filing.get("form") or "").strip().upper()
    stage = str(filing.get("stage") or "").strip().casefold()
    if form != "424B4" or stage != "priced":
        raise QuoteIdentityError(
            f"{company or 'Unknown issuer'} ({ticker or 'no ticker'}): Current Price "
            "is populated before a final 424B4/Priced lifecycle state"
        )
    return company, ticker


def audit_payload(payload, lookup_profile, lookup_sec_profile=None):
    filings = payload.get("filings", []) if isinstance(payload, dict) else []
    profiles, sec_profiles = {}, {}
    audited = 0
    for filing in filings:
        if not isinstance(filing, dict) or filing.get("current_price") in (None, ""):
            continue
        company, ticker = _validate_lifecycle(filing)
        if not company or not ticker:
            raise QuoteIdentityError(
                "Current Price is populated without both issuer name and ticker provenance"
            )
        if ticker not in profiles:
            profiles[ticker] = lookup_profile(ticker)
        _verify_identity(
            filing, profiles[ticker], lookup_sec_profile=lookup_sec_profile,
            sec_profiles=sec_profiles,
        )
        audited += 1
    return audited


def sanitize_payload(payload, lookup_profile, lookup_sec_profile=None):
    """Clear deterministic identity failures; propagate transport/quota failures."""
    filings = payload.get("filings", []) if isinstance(payload, dict) else []
    profiles, sec_profiles = {}, {}
    audited, sanitized = 0, []
    for filing in filings:
        if not isinstance(filing, dict) or filing.get("current_price") in (None, ""):
            continue
        company, ticker = _validate_lifecycle(filing)
        if not company or not ticker:
            _strip_quote_derived_fields(filing)
            sanitized.append((
                company or "Unknown issuer", ticker or "no ticker",
                "missing issuer/ticker provenance",
            ))
            continue
        if ticker not in profiles:
            profiles[ticker] = lookup_profile(ticker)
        try:
            _verify_identity(
                filing, profiles[ticker], lookup_sec_profile=lookup_sec_profile,
                sec_profiles=sec_profiles,
            )
        except QuoteProviderError:
            raise
        except QuoteIdentityError as exc:
            _strip_quote_derived_fields(filing)
            sanitized.append((company, ticker, str(exc)))
            continue
        audited += 1
    return payload, audited, sanitized


def audit_feed(path, api_key=None):
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    quoted = [f for f in payload.get("filings", []) if isinstance(f, dict) and f.get("current_price") not in (None, "")]
    if not quoted:
        print("Market quote identity audit: no populated Current Price values to verify")
        return 0
    api_key = api_key or os.environ.get("MARKET_DATA_API_KEY")
    if not api_key:
        raise QuoteIdentityError(
            "MARKET_DATA_API_KEY is required to verify populated Current Price values"
        )
    sec_user_agent = os.environ.get("SEC_EDGAR_USER_AGENT")
    audited = audit_payload(
        payload,
        lookup_profile=_paced_profile_lookup(api_key),
        lookup_sec_profile=_paced_sec_lookup(sec_user_agent) if sec_user_agent else None,
    )
    print(f"Market quote identity audit passed for {audited} quoted IPOs")
    return audited


def sanitize_feed(path, api_key=None):
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    quoted = [f for f in payload.get("filings", []) if isinstance(f, dict) and f.get("current_price") not in (None, "")]
    if not quoted:
        print("Market quote identity audit: no populated Current Price values to verify")
        return 0, 0
    api_key = api_key or os.environ.get("MARKET_DATA_API_KEY")
    if not api_key:
        raise QuoteProviderError(
            "MARKET_DATA_API_KEY is required to verify populated Current Price values"
        )
    sec_user_agent = os.environ.get("SEC_EDGAR_USER_AGENT")
    payload, audited, sanitized = sanitize_payload(
        payload,
        lookup_profile=_paced_profile_lookup(api_key),
        lookup_sec_profile=_paced_sec_lookup(sec_user_agent) if sec_user_agent else None,
    )
    if sanitized:
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp.replace(path)
        try:
            from dashboard_export import write_dashboard_csv
            write_dashboard_csv(payload.get("filings", []), path)
        except ImportError:
            pass
        for company, ticker, reason in sanitized:
            print(
                f"Market quote identity sanitizer: cleared Current Price for "
                f"{company} ({ticker}): {reason}"
            )
    print(f"Market quote identity gate: {audited} verified; {len(sanitized)} sanitized")
    return audited, len(sanitized)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Verify market-quote issuer identity and clear deterministic "
            "ticker/provider mismatches before release."
        )
    )
    parser.add_argument("feed", help="Path to docs/data/filings.json")
    args = parser.parse_args(argv)
    try:
        sanitize_feed(args.feed)
    except (OSError, json.JSONDecodeError, QuoteIdentityError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
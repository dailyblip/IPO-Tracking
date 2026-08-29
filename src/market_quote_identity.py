"""Fail closed when a market-data ticker resolves to the wrong issuer.

The Research Monitor intentionally treats Current Price as secondary data. SEC
filings establish the IPO identity; a market-data quote is publishable only when
Finnhub's Company Profile 2 endpoint resolves the quoted ticker back to the same
issuer. Deterministic identity failures are sanitized before publication; transient
provider failures still block the release so an outage cannot silently erase data.
"""

import argparse
import json
import os
import re
import time
from pathlib import Path

import requests

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
PROFILE_TIMEOUT_SECONDS = 10
PROFILE_MAX_RETRIES = 4
PROFILE_RETRY_BACKOFF_SECONDS = 5
PROFILE_MIN_INTERVAL_SECONDS = 1.1

_CORPORATE_SUFFIXES = {
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "ltd",
    "limited",
    "plc",
    "llc",
    "lp",
}
_GENERIC_NAME_TOKENS = {
    "group",
    "holdings",
    "holding",
    "financial",
    "technology",
    "technologies",
    "solutions",
    "systems",
    "international",
    "global",
}
_MARKET_VALUE_SIGNAL_MARKERS = (
    "currently valued",
    "current market value",
)


class QuoteIdentityError(RuntimeError):
    """Raised when a populated market quote cannot be tied to the SEC issuer."""


class QuoteProviderError(QuoteIdentityError):
    """Raised when the provider cannot complete an identity lookup reliably."""


def _identity_tokens(name):
    raw_name = str(name or "").strip()
    # SEC company-name strings can carry a terminal state-of-incorporation marker
    # such as ``/DE/``. It is provenance metadata, not part of the issuer identity.
    raw_name = re.sub(r"/[A-Z]{2}/\s*$", "", raw_name, flags=re.IGNORECASE)
    tokens = re.findall(r"[a-z0-9]+", raw_name.casefold())
    while tokens and tokens[-1] in _CORPORATE_SUFFIXES:
        tokens.pop()
    return tokens


def _company_names_match(expected_name, provider_name):
    """Conservatively compare SEC issuer and market-provider company names."""
    expected = _identity_tokens(expected_name)
    provider = _identity_tokens(provider_name)
    if not expected or not provider:
        return False
    if expected == provider:
        return True

    expected_set = set(expected)
    provider_set = set(provider)
    common = expected_set & provider_set
    distinctive_common = common - _GENERIC_NAME_TOKENS
    if not distinctive_common:
        return False

    # Providers sometimes omit one generic trailing word (for example Group or
    # Holdings). Require the shorter identity to otherwise be fully represented.
    smaller, larger = (
        (expected_set, provider_set)
        if len(expected_set) <= len(provider_set)
        else (provider_set, expected_set)
    )
    if len(smaller) >= 2 and smaller <= larger:
        return True

    overlap = len(common) / max(len(expected_set | provider_set), 1)
    return overlap >= 0.8


def _validate_profile(ticker, company_name, profile):
    provider_ticker = str((profile or {}).get("ticker") or "").strip().upper()
    provider_name = str((profile or {}).get("name") or "").strip()
    expected_ticker = str(ticker or "").strip().upper()

    if not provider_ticker or provider_ticker != expected_ticker:
        raise QuoteIdentityError(
            f"{company_name}: market profile ticker {provider_ticker or 'missing'} "
            f"does not match SEC/filing ticker {expected_ticker or 'missing'}"
        )
    if not provider_name:
        raise QuoteIdentityError(
            f"{company_name} ({expected_ticker}): market profile is missing issuer name"
        )
    if not _company_names_match(company_name, provider_name):
        raise QuoteIdentityError(
            f"{company_name} ({expected_ticker}): market profile resolves to "
            f"{provider_name!r}; refusing to publish a possibly collided quote"
        )
    return True


def _retry_delay(response, attempt):
    raw = str((getattr(response, "headers", {}) or {}).get("Retry-After") or "").strip()
    try:
        delay = float(raw)
    except (TypeError, ValueError):
        delay = PROFILE_RETRY_BACKOFF_SECONDS * attempt
    return max(delay, PROFILE_MIN_INTERVAL_SECONDS)


def _fetch_profile(ticker, api_key):
    """Fetch one provider profile, retrying transient quota/server failures."""
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
                time.sleep(_retry_delay(response, attempt))
                continue
            raise QuoteProviderError(
                f"Could not verify market-data identity for {ticker}: "
                f"provider returned HTTP {status} after {PROFILE_MAX_RETRIES} attempts"
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
        # An empty profile is a deterministic provider non-match, not a transport
        # failure. The release sanitizer will clear that ticker's market-derived
        # fields rather than blocking unrelated IPOs.
        return profile

    raise QuoteProviderError(
        f"Could not verify market-data identity for {ticker}: {last_error}"
    )


def _paced_profile_lookup(api_key):
    """Keep identity lookups below Finnhub's free-tier request cadence."""
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


def _strip_quote_derived_fields(filing):
    """Remove a quote and values that are calculated from that quote."""
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


def audit_payload(payload, lookup_profile):
    """Strictly validate every published Current Price against provider identity."""
    filings = payload.get("filings", []) if isinstance(payload, dict) else []
    profiles = {}
    audited = 0
    for filing in filings:
        if not isinstance(filing, dict):
            continue
        if filing.get("current_price") in (None, ""):
            continue

        company = str(filing.get("company") or "").strip()
        ticker = str(filing.get("ticker") or "").strip().upper()
        form = str(filing.get("form") or "").strip().upper()
        stage = str(filing.get("stage") or "").strip().casefold()
        if form != "424B4" or stage != "priced":
            raise QuoteIdentityError(
                f"{company or 'Unknown issuer'} ({ticker or 'no ticker'}): Current Price "
                "is populated before a final 424B4/Priced lifecycle state"
            )
        if not company or not ticker:
            raise QuoteIdentityError(
                "Current Price is populated without both issuer name and ticker provenance"
            )

        if ticker not in profiles:
            profiles[ticker] = lookup_profile(ticker)
        _validate_profile(ticker, company, profiles[ticker])
        audited += 1
    return audited


def sanitize_payload(payload, lookup_profile):
    """Remove deterministic identity failures while preserving verified quotes.

    Provider transport/quota failures are not deterministic and still raise, so a
    temporary Finnhub outage cannot erase otherwise-valid market data.
    """
    filings = payload.get("filings", []) if isinstance(payload, dict) else []
    profiles = {}
    audited = 0
    sanitized = []

    for filing in filings:
        if not isinstance(filing, dict) or filing.get("current_price") in (None, ""):
            continue

        company = str(filing.get("company") or "").strip()
        ticker = str(filing.get("ticker") or "").strip().upper()
        form = str(filing.get("form") or "").strip().upper()
        stage = str(filing.get("stage") or "").strip().casefold()

        # A quote surviving on a pre-pricing record means the earlier canonical
        # sanitizer failed. Treat that as a release-blocking pipeline defect.
        if form != "424B4" or stage != "priced":
            raise QuoteIdentityError(
                f"{company or 'Unknown issuer'} ({ticker or 'no ticker'}): Current Price "
                "is populated before a final 424B4/Priced lifecycle state"
            )

        if not company or not ticker:
            _strip_quote_derived_fields(filing)
            sanitized.append(
                (
                    company or "Unknown issuer",
                    ticker or "no ticker",
                    "missing issuer/ticker provenance",
                )
            )
            continue

        if ticker not in profiles:
            profiles[ticker] = lookup_profile(ticker)
        profile = profiles[ticker]

        try:
            _validate_profile(ticker, company, profile)
        except QuoteIdentityError as exc:
            _strip_quote_derived_fields(filing)
            sanitized.append((company, ticker, str(exc)))
            continue

        audited += 1

    return payload, audited, sanitized


def audit_feed(path, api_key=None):
    """Strict feed audit retained for tests/manual validation."""
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    quoted = [
        filing
        for filing in payload.get("filings", [])
        if isinstance(filing, dict) and filing.get("current_price") not in (None, "")
    ]
    if not quoted:
        print("Market quote identity audit: no populated Current Price values to verify")
        return 0

    api_key = api_key or os.environ.get("MARKET_DATA_API_KEY")
    if not api_key:
        raise QuoteIdentityError(
            "MARKET_DATA_API_KEY is required to verify populated Current Price values"
        )

    audited = audit_payload(payload, lookup_profile=_paced_profile_lookup(api_key))
    print(f"Market quote identity audit passed for {audited} quoted IPOs")
    return audited


def sanitize_feed(path, api_key=None):
    """Release gate: verify quotes and clear deterministic issuer/profile misses."""
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    quoted = [
        filing
        for filing in payload.get("filings", [])
        if isinstance(filing, dict) and filing.get("current_price") not in (None, "")
    ]
    if not quoted:
        print("Market quote identity audit: no populated Current Price values to verify")
        return 0, 0

    api_key = api_key or os.environ.get("MARKET_DATA_API_KEY")
    if not api_key:
        raise QuoteProviderError(
            "MARKET_DATA_API_KEY is required to verify populated Current Price values"
        )

    payload, audited, sanitized = sanitize_payload(
        payload,
        lookup_profile=_paced_profile_lookup(api_key),
    )

    if sanitized:
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
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

    print(
        f"Market quote identity gate: {audited} verified; "
        f"{len(sanitized)} sanitized"
    )
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

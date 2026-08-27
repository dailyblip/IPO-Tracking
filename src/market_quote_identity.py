"""Fail closed when a market-data ticker resolves to the wrong issuer.

The Research Monitor intentionally treats Current Price as secondary data. SEC
filings establish the IPO identity; a market-data quote is publishable only when
Finnhub's free Company Profile 2 endpoint resolves the quoted ticker back to the
same issuer. This catches ticker reuse/provider collisions without guessing.
"""

import argparse
import json
import os
import re
from pathlib import Path

import requests

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
PROFILE_TIMEOUT_SECONDS = 10

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


class QuoteIdentityError(RuntimeError):
    """Raised when a populated market quote cannot be tied to the SEC issuer."""


def _identity_tokens(name):
    tokens = re.findall(r"[a-z0-9]+", str(name or "").casefold())
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


def _fetch_profile(ticker, api_key):
    try:
        response = requests.get(
            f"{FINNHUB_BASE_URL}/stock/profile2",
            params={"symbol": ticker, "token": api_key},
            timeout=PROFILE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        profile = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise QuoteIdentityError(
            f"Could not verify market-data identity for {ticker}: {exc}"
        ) from exc
    if not isinstance(profile, dict) or not profile:
        raise QuoteIdentityError(
            f"Could not verify market-data identity for {ticker}: empty company profile"
        )
    return profile


def audit_payload(payload, lookup_profile):
    """Validate every published Current Price against the provider issuer profile."""
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


def audit_feed(path, api_key=None):
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

    audited = audit_payload(
        payload,
        lookup_profile=lambda ticker: _fetch_profile(ticker, api_key),
    )
    print(f"Market quote identity audit passed for {audited} quoted IPOs")
    return audited


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify that every published market quote resolves to the SEC IPO issuer."
    )
    parser.add_argument("feed", help="Path to docs/data/filings.json")
    args = parser.parse_args(argv)
    try:
        audit_feed(args.feed)
    except (OSError, json.JSONDecodeError, QuoteIdentityError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()

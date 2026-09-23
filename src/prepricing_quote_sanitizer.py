"""Sanitize unsafe market/final-price fields and public holder currency precision.

Ticker symbols can collide with already-trading securities before an IPO begins
trading. Publishing those provider quotes on an S-1/S-1A record is therefore a
data-integrity defect. Current Price is allowed only when a final 424B4 row also
has a priced lifecycle state, an authoritative pricing date, a positive final
IPO price, and a positive current quote observed no earlier than the final SEC
filing date. Public feed rows with an explicitly blank ticker also fail closed:
a market quote without the ticker identity used to retrieve it has no release-safe
provider provenance. A malformed/incomplete lifecycle or a priced row without a
publishable quote must fail closed and lose market-derived holder values rather
than retaining stale quote arithmetic.

A genuine pre-pricing S-1/S-1/A also cannot retain stale final-pricing metadata from
an earlier or mismatched lifecycle state. Clear Final IPO Price, holder IPO-value /
realized-cash derivatives, and final-pricing signals while preserving authoritative
preliminary Filing Price/range and SEC-supported ownership facts. This repairs the
impossible fields instead of forcing an otherwise qualifying registration out of the
public feed.

Public holder currency values are also normalized to cents before release. They
are arithmetic outputs, not additional source evidence, and binary floating-point
tails must not leak into JSON/CSV output. Share counts and per-share market/IPO
prices are left untouched.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


_MARKET_VALUE_SIGNAL_MARKERS = ("currently valued", "current market value")
_FINAL_PRICING_SIGNAL_MARKERS = (
    "offering priced at",
    "offering raised approximately",
)
_MARKET_DERIVED_PERSON_FIELDS = (
    "cash_value",
    "liquid_value",
    "locked_value",
    "valuation_as_of",
)
_FINAL_PRICE_DERIVED_PERSON_FIELDS = (
    "ipo_value",
    "cash_realized_ipo",
)
_PUBLIC_PERSON_CURRENCY_FIELDS = (
    "cash_value",
    "ipo_value",
    "liquid_value",
    "locked_value",
    "cash_realized_ipo",
)
_SEC_FILING_TIMEZONE = ZoneInfo("America/New_York")


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalize_public_person_currency(person: dict) -> bool:
    """Remove binary-float tails from public holder dollar amounts only."""
    changed = False
    for field in _PUBLIC_PERSON_CURRENCY_FIELDS:
        if field not in person or person.get(field) in (None, ""):
            continue
        number = _number(person.get(field))
        if number is None:
            continue
        normalized = round(number, 2)
        if person.get(field) != normalized:
            person[field] = normalized
            changed = True
    return changed


def _canonical_nonfuture_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.isoformat() != raw or parsed > date.today():
        return None
    return parsed


def _canonical_quote_date(value):
    """Return the SEC Eastern date for an explicit, non-future quote timestamp.

    ``price_updated`` is the provenance marker for Current Price. A quote without a
    parseable timezone-aware timestamp cannot establish when the market value was
    observed, so it must fail closed. The normalized UTC timestamp itself must not
    be in the future, including later on the same UTC date. The final comparison uses
    the SEC/market Eastern calendar so a just-after-midnight UTC quote cannot masquerade
    as occurring on the following SEC filing date.
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    quote_time = parsed.astimezone(timezone.utc)
    if quote_time > datetime.now(timezone.utc):
        return None
    return quote_time.astimezone(_SEC_FILING_TIMEZONE).date()


def _is_prepricing_registration(filing: dict) -> bool:
    """Treat every S-1/S-1/A as pre-pricing regardless of stale stage metadata.

    The SEC form is the authoritative lifecycle signal here. A stale merge can label
    an S-1/S-1/A row ``Priced`` after a later 424B4 was seen, but the registration
    statement itself still cannot support final IPO price, realized-cash, or live
    market-price fields. Fail closed on the form instead of trusting a mismatched
    stage label.
    """
    return str(filing.get("form") or "").strip().upper() in {"S-1", "S-1/A"}


def is_priced_ipo(filing: dict) -> bool:
    """Return True only for a release-safe final priced lifecycle state."""
    if str(filing.get("form") or "").strip().upper() != "424B4":
        return False
    if str(filing.get("stage") or "").strip().casefold() != "priced":
        return False
    pricing_date = _canonical_nonfuture_date(filing.get("pricing_date"))
    if pricing_date is None:
        return False

    # ``filed`` is the SEC filing date of the current public row. ``filing_date``
    # is the original S-1 date and must not be used for this comparison. A final
    # 424B4 without a canonical SEC filing date is not release-safe, and a pricing
    # date after that filing date is impossible. In either case the row must not
    # retain a live quote even if an earlier sanitizer was bypassed or ordering
    # changes later.
    filed_date = _canonical_nonfuture_date(filing.get("filed"))
    if filed_date is None or pricing_date > filed_date:
        return False

    final_price = _number(filing.get("offering_price"))
    return final_price is not None and final_price > 0


def has_release_safe_market_quote(filing: dict) -> bool:
    """Require a safely priced lifecycle plus a chronologically valid live quote."""
    if not is_priced_ipo(filing):
        return False

    # The V1 public schema always carries a ticker key, even when the symbol is not
    # yet known. An explicitly blank ticker cannot support provider identity or a
    # ticker-keyed quote lookup, so fail closed on public rows instead of preserving
    # an unverifiable Current Price. Lightweight internal/unit fixtures that omit the
    # field entirely retain their existing behavior; schema validation separately
    # requires the key on published rows.
    if "ticker" in filing and not str(filing.get("ticker") or "").strip():
        return False

    current_price = _number(filing.get("current_price"))
    if current_price is None or current_price <= 0:
        return False

    filed_date = _canonical_nonfuture_date(filing.get("filed"))
    quote_date = _canonical_quote_date(filing.get("price_updated"))
    # A quote dated before the final 424B4 can belong to an already-trading security
    # that reused the pending IPO's ticker. The SEC filing date is the earliest
    # unambiguous day this public row is in a verified final state, so older provider
    # quotes fail closed. Same-day final-filing quotes remain eligible for the later
    # exact SEC acceptance-time gate.
    return bool(filed_date and quote_date and quote_date >= filed_date)


def sanitize_payload(payload: dict) -> tuple[dict, int]:
    changed = 0
    for filing in payload.get("filings", []):
        if not isinstance(filing, dict):
            continue

        touched = False
        prepricing_registration = _is_prepricing_registration(filing)

        # An S-1/S-1/A registration cannot carry completed-offering facts even when
        # a stale merge mislabeled its stage as Priced. Preserve preliminary Filing
        # Price/range, size evidence, and ownership; clear only fields whose meaning
        # depends on the IPO already having priced.
        if prepricing_registration:
            if filing.get("offering_price") not in (None, ""):
                filing.pop("offering_price", None)
                touched = True

            for person in filing.get("people", []):
                if not isinstance(person, dict):
                    continue
                for field in _FINAL_PRICE_DERIVED_PERSON_FIELDS:
                    if field in person:
                        person.pop(field, None)
                        touched = True

            signals = filing.get("signals")
            if isinstance(signals, list):
                filtered_signals = [
                    signal
                    for signal in signals
                    if not (
                        isinstance(signal, str)
                        and any(
                            marker in signal.casefold()
                            for marker in _FINAL_PRICING_SIGNAL_MARKERS
                        )
                    )
                ]
                if len(filtered_signals) != len(signals):
                    filing["signals"] = filtered_signals
                    touched = True

        quote_safe = has_release_safe_market_quote(filing)
        if not quote_safe:
            for field in ("current_price", "price_updated"):
                if field in filing:
                    filing.pop(field, None)
                    touched = True

            # Without a release-safe filing-level quote, holder-level current market
            # values have no publishable basis. Preserve SEC-supported ownership facts,
            # IPO-value arithmetic, and realized IPO cash on valid priced records; for
            # S-1/S-1/A rows those final-price derivatives were cleared above.
            for person in filing.get("people", []):
                if not isinstance(person, dict):
                    continue
                for field in _MARKET_DERIVED_PERSON_FIELDS:
                    if field in person:
                        person.pop(field, None)
                        touched = True

            # A stale public signal can imply that a current quote still exists even
            # after the quote itself is absent. Remove every known market-value wording,
            # not only the legacy "Largest named holding" sentence.
            signals = filing.get("signals")
            if isinstance(signals, list):
                filtered_signals = [
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
                if len(filtered_signals) != len(signals):
                    filing["signals"] = filtered_signals
                    touched = True

        # Currency fields that survive the release-safety checks are public dollar
        # amounts. Normalize only those derived amounts to cents; do not alter share
        # counts or per-share current/final IPO prices, which may validly use finer
        # precision.
        for person in filing.get("people", []):
            if isinstance(person, dict) and _normalize_public_person_currency(person):
                touched = True

        if touched:
            changed += 1
    return payload, changed


def sanitize_file(path: str | Path) -> int:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload, changed = sanitize_payload(payload)
    if changed:
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp.replace(path)
        try:
            from dashboard_export import write_dashboard_csv
            write_dashboard_csv(payload.get("filings", []), path)
        except ImportError:
            pass
    return changed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sanitize unsafe market/final-pricing fields and public holder currency precision")
    parser.add_argument("path", nargs="?", default="../docs/data/filings.json")
    args = parser.parse_args()
    count = sanitize_file(args.path)
    print(f"Sanitized {count} filing(s) with market/final-pricing/currency cleanup")

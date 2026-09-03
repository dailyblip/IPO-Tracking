"""Suppress person-level economic derivatives that public SEC evidence cannot attribute.

The Research Monitor may preserve an SEC-reported beneficial-ownership share count
while declining to turn that count into personal paper value, liquidity, or realized
cash when the filing explicitly says the shares are held by other entities and the
reporting person disclaims beneficial ownership except for an undisclosed pecuniary
interest. It also rejects holder-level IPO sale economics that contradict the same
holder's disclosed pre-IPO position. Incorrect personal economics are worse than a
blank derived value.

The issuer-specific registry is intentionally narrow. Each entry must be tied to a
specific issuer, IPO accession, holder identity, disclosed share count, and primary
SEC evidence.
"""

from __future__ import annotations

import math

from ownership_parser import canonical_holder_name


# SEC Form 3 filed 2026-06-11 by Antonio J. Gracias for SpaceX states that the
# 503,414,530 reported shares are held of record by 30 Valor entities. It says he
# may be deemed to beneficially own those shares because of his positions with the
# entities/general partners and that he disclaims beneficial ownership except to
# the extent of his pecuniary interest. The filing does not quantify that personal
# pecuniary interest, so the Monitor must not publish the full position's value or
# liquidity as Antonio Gracias's personal economics.
# https://www.sec.gov/Archives/edgar/data/1495158/000162828026042633/xslF345X03/wk-form3_1781226087.xml
_UNSUPPORTED_PERSON_ECONOMICS = {
    (
        "0001181412",
        "0001628280-26-042639",
        canonical_holder_name("Antonio J. Gracias"),
    ): 503_414_530,
}

_DERIVED_ECONOMIC_FIELDS = (
    "cash_value",
    "ipo_value",
    "liquid_shares",
    "liquid_value",
    "locked_shares",
    "locked_value",
    "cash_realized_ipo",
    "valuation_as_of",
)


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _money(value):
    value = _number(value)
    if value is None or value <= 0:
        return None
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def suppress_unsupported_person_economics(filing: dict) -> dict:
    """Return a copy with unsupported person-level economic derivatives cleared.

    The SEC-reported beneficial-owner share quantity remains a public fact even when
    economic attribution is unsupported. Separately, when the same holder has an
    authoritative pre-IPO share count, a claimed IPO sale cannot exceed that position;
    impossible sale/realized-cash fields fail closed while the underlying ownership
    facts remain intact.

    Issuer-specific registry entries apply only while the exact disclosed share count
    still matches, so later authoritative ownership changes do not inherit a stale
    exception silently.
    """
    if not isinstance(filing, dict):
        return filing

    cik = str(filing.get("cik") or "").strip()
    accession = str(filing.get("accession_no") or "").strip()
    people = filing.get("people")
    if not isinstance(people, list):
        return dict(filing)

    normalized = dict(filing)
    normalized_people = []
    changed = False
    position_value_suppressed = False

    for person in people:
        if not isinstance(person, dict):
            normalized_people.append(person)
            continue

        normalized_person = dict(person)

        shares_before_ipo = _number(person.get("shares_before_ipo"))
        shares_sold_ipo = _number(person.get("shares_sold_ipo"))
        if (
            shares_before_ipo is not None
            and shares_before_ipo >= 0
            and shares_sold_ipo is not None
            and shares_sold_ipo > shares_before_ipo
        ):
            for field in ("shares_sold_ipo", "cash_realized_ipo"):
                if normalized_person.get(field) not in (None, ""):
                    normalized_person[field] = None
                    changed = True

        key = (cik, accession, canonical_holder_name(person.get("name")))
        expected_shares = _UNSUPPORTED_PERSON_ECONOMICS.get(key)
        observed_shares = _number(person.get("shares"))

        if expected_shares is not None and observed_shares == float(expected_shares):
            for field in _DERIVED_ECONOMIC_FIELDS:
                if normalized_person.get(field) not in (None, ""):
                    normalized_person[field] = None
                    changed = True
                    position_value_suppressed = True

        normalized_people.append(normalized_person)

    if not changed:
        return normalized

    normalized["people"] = normalized_people

    # Keep the filing-level largest-holding signal synchronized only when a holder's
    # paper-value field was suppressed. Sale-only repairs do not alter current values.
    if position_value_suppressed:
        signals = filing.get("signals")
        if isinstance(signals, list):
            prefix = "Largest named holding currently valued at approximately "
            remaining_values = [
                _number(person.get("cash_value"))
                for person in normalized_people
                if isinstance(person, dict)
            ]
            remaining_values = [value for value in remaining_values if value is not None and value > 0]
            replacement = f"{prefix}{_money(max(remaining_values))}" if remaining_values else None
            updated_signals = []
            replaced = False
            for signal in signals:
                if isinstance(signal, str) and signal.startswith(prefix):
                    if replacement and not replaced:
                        updated_signals.append(replacement)
                        replaced = True
                    continue
                updated_signals.append(signal)
            normalized["signals"] = updated_signals

    return normalized

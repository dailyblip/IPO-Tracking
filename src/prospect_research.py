"""Prospect Research normalization helpers.

Keeps researcher-facing classifications conservative: when a fact is not
explicitly present in the source row, return Unknown rather than infer wealth
or liquidity.
"""
from __future__ import annotations

import re

ENTITY_MARKERS = (
    " lp", " l.p.", " llc", " ltd", " limited", " inc", " corp", " corporation",
    " fund", " partners", " partnership", " capital", " ventures", " holdings",
    " trust", " foundation", " bank", " management", " advisors", " nominees",
)
FUND_MARKERS = (" fund", " capital", " ventures", " partners", " partnership", " lp", " l.p.")
TRUST_MARKERS = (" trust", " trustee")


def holder_type(name: str) -> str:
    """Classify a beneficial-owner row without pretending entities are people."""
    value = " ".join(str(name or "").split()).lower()
    if not value:
        return "Unknown"
    if any(marker in value for marker in TRUST_MARKERS):
        return "Trust"
    if any(marker in value for marker in FUND_MARKERS):
        return "Fund"
    if any(marker in value for marker in ENTITY_MARKERS):
        return "Entity"
    # SEC natural-person rows are usually 2-5 alphabetic name tokens.
    tokens = [t for t in re.split(r"\s+", value) if re.search(r"[a-z]", t)]
    return "Individual" if 2 <= len(tokens) <= 6 else "Unknown"


def first_present(row: dict, *keys):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def confirmed_boolean(value) -> bool:
    """Return True only for explicit affirmative values.

    Avoid Python's bool("False") == True trap for spreadsheet/string-backed
    fields used to drive researcher-facing Stanford affiliation flags.
    """
    if value is True:
        return True
    if value is False or value in (None, ""):
        return False
    if isinstance(value, (int, float)):
        return value == 1
    return str(value).strip().lower() in {"true", "yes", "y", "1"}


def prospect_person_metadata(row: dict, name: str) -> dict:
    """Normalize fields useful to a prospect researcher when upstream provides them."""
    stanford_confirmed = confirmed_boolean(
        first_present(row, "Stanford Affiliation Confirmed", "Stanford University in Bio")
    )
    return {
        "holder_type": holder_type(name),
        "role": first_present(row, "Role", "Title", "Position", "Relationship"),
        "ownership_percent": first_present(row, "Ownership % After IPO", "Ownership %", "Percent Ownership", "Percent", "% Ownership"),
        "ownership_percent_before": first_present(row, "Ownership % Before IPO", "Percent Before IPO"),
        "ownership_percent_after": first_present(row, "Ownership % After IPO", "Percent After IPO", "Ownership %", "Percent Ownership"),
        "shares_before_ipo": first_present(row, "Shares Before IPO", "Shares Before Offering"),
        "shares_sold_ipo": first_present(row, "Shares Sold in IPO", "Shares Offered", "Secondary Shares"),
        "shares_after_ipo": first_present(row, "Shares After IPO", "Shares After Offering", "Shares"),
        "stanford_source": first_present(row, "Stanford Justification", "Stanford Source"),
        "stanford_affiliation_confirmed": stanford_confirmed,
        # Backward-compatible public/UI field. Keep it derived from the confirmed
        # affiliation gate so researcher-facing Stanford highlighting cannot be
        # driven by an unconfirmed or false-like raw source value.
        "stanford_university_bio": stanford_confirmed,
        "common_shares": first_present(row, "Common Shares"),
        "restricted_shares": first_present(row, "Restricted Shares", "Unvested Shares"),
        "options_shares": first_present(row, "Option Shares", "Options Exercisable"),
    }

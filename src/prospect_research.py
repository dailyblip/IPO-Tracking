"""Prospect Research normalization helpers.

Keeps researcher-facing classifications conservative: when a fact is not
explicitly present in the source row, return Unknown rather than infer wealth
or liquidity.
"""
from __future__ import annotations

import math
import re

ENTITY_MARKERS = (
    " lp", " l.p.", " llc", " ltd", " limited", " inc", " corp", " corporation",
    " fund", " partners", " partnership", " capital", " ventures", " holdings",
    " trust", " foundation", " bank", " management", " advisors", " nominees",
    " authority", " university", " college", " institute", " association",
    " pension", " retirement system", " endowment", " government", " ministry",
)
FUND_MARKERS = (" fund", " capital", " ventures", " partners", " partnership", " lp", " l.p.")
TRUST_MARKERS = (" trust", " trustee")
AGGREGATE_ENTITY_MARKERS = (
    "entities affiliated with",
    "affiliated entities",
    "funds affiliated with",
    "affiliates of",
)


def holder_type(name: str) -> str:
    """Classify a beneficial-owner row without pretending entities are people."""
    value = " ".join(str(name or "").split()).lower()
    if not value:
        return "Unknown"
    # SEC ownership tables often aggregate several affiliated legal entities into
    # one disclosure row. Treat those labels as entities regardless of whether
    # the underlying sponsor name contains words such as Capital or Ventures.
    if any(marker in value for marker in AGGREGATE_ENTITY_MARKERS):
        return "Entity"
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


def _metric_number(value):
    """Parse an explicit ownership metric without inferring a missing value."""
    if value is None or isinstance(value, bool):
        return None
    raw = str(value).strip().replace(",", "").replace("%", "")
    if not raw:
        return None
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def valid_ownership_percent(value):
    """Preserve a disclosed percent only when it is numerically possible."""
    number = _metric_number(value)
    if number is None or number < 0 or number > 100:
        return None
    return value


def valid_share_count(value):
    """Preserve a disclosed share count only when it is a non-negative whole number."""
    number = _metric_number(value)
    if number is None or number < 0 or not number.is_integer():
        return None
    return value


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


def _stanford_public_source(row: dict):
    """Publish concise Stanford research context with the grader's 1-5 score.

    The score is evidence confidence, not connection strength. Grade 5 is the
    only confirmed state; 1-4 remain research leads and never drive red text.
    """
    note = first_present(row, "Stanford Justification", "Stanford Source")
    grade = first_present(row, "Stanford Grade")
    try:
        grade = int(grade)
    except (TypeError, ValueError):
        grade = None
    if note and grade in {1, 2, 3, 4, 5}:
        return f"Confidence {grade}/5 — {str(note).strip()}"
    return note


def prospect_person_metadata(row: dict, name: str) -> dict:
    """Normalize fields useful to a prospect researcher when upstream provides them.

    Ownership-table HTML can contain complex colspans and spacer columns. If an
    upstream column alignment ever places a share count in a percentage field (or
    a percentage in a share-count field), fail closed here rather than publishing
    an impossible researcher-facing metric. We deliberately do not swap or infer
    values; unverifiable fields stay blank until the SEC table is parsed correctly.
    """
    stanford_confirmed = confirmed_boolean(
        first_present(row, "Stanford Affiliation Confirmed", "Stanford University in Bio")
    )
    ownership_percent = valid_ownership_percent(
        first_present(row, "Ownership % After IPO", "Ownership %", "Percent Ownership", "Percent", "% Ownership")
    )
    ownership_percent_before = valid_ownership_percent(
        first_present(row, "Ownership % Before IPO", "Percent Before IPO")
    )
    ownership_percent_after = valid_ownership_percent(
        first_present(row, "Ownership % After IPO", "Percent After IPO", "Ownership %", "Percent Ownership")
    )
    return {
        "holder_type": holder_type(name),
        "role": first_present(row, "Role", "Title", "Position", "Relationship"),
        "ownership_percent": ownership_percent,
        "ownership_percent_before": ownership_percent_before,
        "ownership_percent_after": ownership_percent_after,
        "shares_before_ipo": valid_share_count(first_present(row, "Shares Before IPO", "Shares Before Offering")),
        "shares_sold_ipo": valid_share_count(first_present(row, "Shares Sold in IPO", "Shares Offered", "Secondary Shares")),
        "shares_after_ipo": valid_share_count(first_present(row, "Shares After IPO", "Shares After Offering", "Shares")),
        "stanford_source": _stanford_public_source(row),
        "stanford_affiliation_confirmed": stanford_confirmed,
        # Backward-compatible public/UI field. Keep it derived from the confirmed
        # affiliation gate so researcher-facing Stanford highlighting cannot be
        # driven by an unconfirmed or false-like raw source value.
        "stanford_university_bio": stanford_confirmed,
        "common_shares": valid_share_count(first_present(row, "Common Shares")),
        "restricted_shares": valid_share_count(first_present(row, "Restricted Shares", "Unvested Shares")),
        "options_shares": valid_share_count(first_present(row, "Option Shares", "Options Exercisable")),
    }

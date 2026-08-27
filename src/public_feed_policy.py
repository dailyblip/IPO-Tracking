"""Release policy gate for the public Research Monitor feed."""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

from dashboard_export import write_dashboard_csv
from edgar_client import INVESTMENT_PRODUCT_NAME_PATTERN, SPAC_NAME_PATTERN
from ownership_parser import looks_like_document_heading
from prepricing_quote_sanitizer import sanitize_payload as sanitize_prepricing_quotes
from prospect_research import holder_type, valid_ownership_percent, valid_share_count

# Retained as a reusable UI/filter threshold; it is no longer a publication gate.
MINIMUM_IPO_VALUE = 100_000_000.0
SUPPORTED_IPO_FORMS = {"S-1", "S-1/A", "424B4"}
_STANFORD_OPERATIONAL_ERROR_MARKERS = (
    "grading failed to run:",
    "stanford research request failed",
    "insufficient_quota",
    "credit_balance_exhausted",
    "no credits remaining",
    "person-level stanford grading skipped",
)


def _number(value):
    """Parse only explicit numeric values; never infer or estimate a missing size."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


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


def _iso_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def _sanitize_impossible_lifecycle_date(filing):
    """Clear an impossible initial filing date without inventing a replacement.

    ``filed`` is the canonical SEC date for the specific public row/form. The
    separate ``filing_date`` field is the lifecycle's initial S-1 date carried
    forward across amendments and 424B4 promotion. Historical merges can retain a
    stale initial date from a later filing. If that carried date is after an
    authoritative pricing date, clear only the impossible lifecycle field.

    This normalization lives in the release gate so every publisher that invokes
    public-feed policy gets the same protection, not only the daily workflow.
    """
    normalized = dict(filing)
    pricing_date = _iso_date(filing.get("pricing_date"))
    filing_date = _iso_date(filing.get("filing_date"))
    if pricing_date and filing_date and filing_date > pricing_date:
        normalized["filing_date"] = None
    return normalized


def _has_valid_filing_date(filing):
    """Require a canonical, non-future SEC filing date for every public row."""
    filed = str((filing or {}).get("filed") or "").strip()
    if len(filed) != 10:
        return False
    try:
        parsed = date.fromisoformat(filed)
    except ValueError:
        return False
    return parsed.isoformat() == filed and parsed <= date.today()


def _has_supported_ipo_form(filing):
    """Fail closed unless the record is a supported operating-company IPO form.

    The monitor is intentionally limited to S-1/S-1/A registration statements and
    final 424B4 prospectuses. Other Securities Act forms can represent follow-on,
    resale, shelf, fund, or other non-IPO registrations and must not qualify solely
    because they carry a large dollar value.
    """
    form = str((filing or {}).get("form") or "").strip().upper()
    return form in SUPPORTED_IPO_FORMS


def _has_excluded_issuer_name(filing):
    """Fail closed for issuer names that independently identify excluded products.

    Full SPAC/reverse-SPAC/investment-product detection remains upstream because it
    can inspect filing text. This release gate adds a final deterministic safeguard
    for name patterns that are strong enough to classify without inference.
    """
    company = str((filing or {}).get("company") or "").strip()
    return bool(
        SPAC_NAME_PATTERN.search(company)
        or INVESTMENT_PRODUCT_NAME_PATTERN.search(company)
    )


def _has_safe_s1_size_provenance(filing):
    """Reject unsafe S-1 size arithmetic without making size a publication gate.

    A preliminary range is inherently offering-specific. For fixed-price S-1 rows
    with a populated offering value, require explicit issuer-offering provenance
    before trusting that numeric value. Selling-stockholder/resale language always
    wins over generic cover-page wording. If no numeric size is known, do not reject
    an otherwise qualifying IPO merely for the missing size; upstream IPO/product
    classification and the resale markers below remain the safeguards.
    """
    form = str((filing or {}).get("form") or "").strip().upper()
    if form not in {"S-1", "S-1/A"}:
        return True

    source = str((filing or {}).get("offering_size_source") or "").strip().lower()
    resale_markers = (
        "selling stockholder",
        "selling shareholder",
        "selling securityholder",
        "resale",
        "secondary-only",
        "secondary only",
    )
    if any(marker in source for marker in resale_markers):
        return False

    value = _number((filing or {}).get("value"))
    if value is None:
        return True

    price_range = str((filing or {}).get("price_range") or "").strip()
    if price_range:
        return True

    confidence = str((filing or {}).get("offering_size_confidence") or "").strip().lower()
    issuer_markers = (
        "issuer-only",
        "issuer only",
        "issuer offering",
        "company offering",
        "primary offering",
    )
    return confidence == "high" and any(marker in source for marker in issuer_markers)


def _has_consistent_priced_offering_value(filing):
    """Reject priced IPOs whose stored value conflicts with exact offering arithmetic.

    When the feed already contains an explicit final IPO price and exact offering
    share counts, those authoritative facts must reconcile with the published
    offering value. We intentionally do not infer a missing secondary component.
    A single known primary count is therefore cross-checked only when provenance
    explicitly says the offering is issuer-only. If both primary and secondary
    counts are present, the combined base offering is cross-checked. Greenshoe or
    over-allotment shares are not part of this base calculation.
    """
    form = str((filing or {}).get("form") or "").strip().upper()
    if form != "424B4":
        return True

    published_value = _number((filing or {}).get("value"))
    final_price = _number((filing or {}).get("offering_price"))
    primary = _number((filing or {}).get("primary_offering_shares"))
    secondary = _number((filing or {}).get("secondary_offering_shares"))
    if published_value is None or final_price is None or final_price <= 0 or primary is None or primary < 0:
        return True

    source = str((filing or {}).get("offering_size_source") or "").strip().lower()
    if secondary is None:
        issuer_only = "issuer-only" in source or "issuer only" in source
        if not issuer_only:
            return True
        base_shares = primary
    else:
        if secondary < 0:
            return False
        base_shares = primary + secondary

    derived_value = base_shares * final_price
    tolerance = max(1.0, derived_value * 0.001)
    return abs(published_value - derived_value) <= tolerance


def _remove_document_heading_people(filing):
    """Remove stale prospectus section labels from retained owner lists.

    Parser fixes only protect rows that are rebuilt. Rolling-window refreshes can
    preserve older public records, so apply the same conservative heading detector
    at the canonical release gate. Only explicit document headings are removed;
    uppercase fund/corporate owner names remain eligible. Keep the deterministic
    owner-count metadata and signal synchronized with the filtered list.
    """
    normalized = dict(filing)
    people = filing.get("people")
    if not isinstance(people, list):
        return normalized

    filtered = []
    removed = 0
    for person in people:
        if isinstance(person, dict) and looks_like_document_heading(person.get("name")):
            removed += 1
            continue
        filtered.append(person)

    if not removed:
        return normalized

    normalized["people"] = filtered
    normalized["people_count"] = len(filtered)

    signals = filing.get("signals")
    if isinstance(signals, list):
        count_suffix = " named beneficial owners disclosed"
        normalized_signals = []
        count_replaced = False
        for signal in signals:
            if isinstance(signal, str) and signal.strip().endswith(count_suffix):
                if filtered and not count_replaced:
                    normalized_signals.append(f"{len(filtered)}{count_suffix}")
                    count_replaced = True
                continue
            if not filtered and isinstance(signal, str) and signal.startswith(
                "Largest named holding currently valued at approximately "
            ):
                continue
            normalized_signals.append(signal)
        normalized["signals"] = normalized_signals
    return normalized


def _normalize_people_types(filing):
    """Correct deterministic owner-type mismatches before public release.

    Generated feed files can temporarily lag parser improvements. Reclassify only
    from the published beneficial-owner label itself, using the same conservative
    helper as the main pipeline. This does not infer identity or affiliation; it
    prevents obvious organization/aggregate rows from being shown as individuals.
    Return copies rather than mutating the input so persistence changes remain
    detectable by the release gate.
    """
    normalized = dict(filing)
    people = filing.get("people")
    if not isinstance(people, list):
        return normalized

    normalized_people = []
    for person in people:
        if not isinstance(person, dict):
            normalized_people.append(person)
            continue
        normalized_person = dict(person)
        name = str(person.get("name") or "").strip()
        if name:
            normalized_person["holder_type"] = holder_type(name)
        normalized_people.append(normalized_person)
    normalized["people"] = normalized_people
    return normalized


def _normalize_person_ownership_metrics(filing):
    """Fail closed on impossible public ownership metrics across the entire feed.

    The upstream row normalizer protects newly rebuilt records, but historical rows
    can survive a rolling-window refresh without being reconstructed. Apply the same
    conservative numeric checks at the canonical release gate so stale malformed
    percentage/share fields cannot remain public indefinitely. No values are swapped,
    inferred, or repaired by position; invalid metrics are cleared only.
    """
    normalized = dict(filing)
    people = filing.get("people")
    if not isinstance(people, list):
        return normalized

    percent_fields = (
        "ownership_percent",
        "ownership_percent_before",
        "ownership_percent_after",
    )
    share_fields = (
        "shares",
        "shares_before_ipo",
        "shares_sold_ipo",
        "shares_after_ipo",
        "liquid_shares",
        "locked_shares",
    )
    derived_value_fields = {
        "shares": ("cash_value",),
        "liquid_shares": ("liquid_value",),
        "locked_shares": ("locked_value",),
    }

    normalized_people = []
    for person in people:
        if not isinstance(person, dict):
            normalized_people.append(person)
            continue
        normalized_person = dict(person)
        for field in percent_fields:
            if field in normalized_person:
                normalized_person[field] = valid_ownership_percent(normalized_person.get(field))
        for field in share_fields:
            if field not in normalized_person:
                continue
            original = normalized_person.get(field)
            sanitized = valid_share_count(original)
            normalized_person[field] = sanitized
            if original not in (None, "") and sanitized is None:
                for value_field in derived_value_fields.get(field, ()):
                    normalized_person[value_field] = None
        normalized_people.append(normalized_person)
    normalized["people"] = normalized_people
    return normalized


def _scrub_stanford_operational_errors(filing):
    """Keep internal Stanford-processing text out of public person records.

    Historical rows may retain an error or deterministic processing note from an
    earlier grading attempt. Such strings are not public evidence and must never be
    rendered as a Stanford connection source. Confirmed evidence notes and affiliation
    flags are preserved unchanged.
    """
    normalized = dict(filing)
    people = filing.get("people")
    if not isinstance(people, list):
        return normalized

    normalized_people = []
    for person in people:
        if not isinstance(person, dict):
            normalized_people.append(person)
            continue
        normalized_person = dict(person)
        source = str(person.get("stanford_source") or "").strip()
        folded = source.casefold()
        if source and any(marker in folded for marker in _STANFORD_OPERATIONAL_ERROR_MARKERS):
            normalized_person["stanford_source"] = ""
        normalized_people.append(normalized_person)
    normalized["people"] = normalized_people
    return normalized


def _normalize_market_value_consistency(filing):
    """Keep quote-derived owner values, dates, and public signals synchronized.

    Market-price refreshes can legitimately change after a filing record is built.
    Recompute only deterministic arithmetic from the already-published current quote
    and disclosed share quantities. Never manufacture a quote or share count.
    """
    normalized = dict(filing)
    current_price = _number(filing.get("current_price"))
    if current_price is None or current_price <= 0:
        return normalized

    price_updated = str(filing.get("price_updated") or "").strip()
    valuation_as_of = price_updated[:10] if len(price_updated) >= 10 else None
    people = filing.get("people")
    if not isinstance(people, list):
        return normalized

    normalized_people = []
    largest_holding = 0.0
    for person in people:
        if not isinstance(person, dict):
            normalized_people.append(person)
            continue
        normalized_person = dict(person)
        shares = _number(person.get("shares"))
        if shares is not None and shares >= 0:
            normalized_person["cash_value"] = shares * current_price
            if valuation_as_of:
                normalized_person["valuation_as_of"] = valuation_as_of
            liquid_shares = _number(person.get("liquid_shares"))
            if liquid_shares is not None and liquid_shares >= 0:
                normalized_person["liquid_value"] = liquid_shares * current_price
            locked_shares = _number(person.get("locked_shares"))
            if locked_shares is not None and locked_shares >= 0:
                normalized_person["locked_value"] = locked_shares * current_price
            largest_holding = max(largest_holding, normalized_person["cash_value"])
        normalized_people.append(normalized_person)
    normalized["people"] = normalized_people

    signals = filing.get("signals")
    if isinstance(signals, list):
        prefix = "Largest named holding currently valued at approximately "
        replacement = f"{prefix}{_money(largest_holding)}" if largest_holding > 0 else None
        normalized_signals = []
        replaced = False
        for signal in signals:
            if isinstance(signal, str) and signal.startswith(prefix):
                if replacement and not replaced:
                    normalized_signals.append(replacement)
                    replaced = True
                continue
            normalized_signals.append(signal)
        normalized["signals"] = normalized_signals
    return normalized


def qualifies_for_public_feed(filing):
    """Return True for qualifying operating-company IPOs regardless of offering size."""
    if not isinstance(filing, dict):
        return False
    if not _has_supported_ipo_form(filing):
        return False
    if _has_excluded_issuer_name(filing):
        return False
    if not _has_safe_s1_size_provenance(filing):
        return False
    if not _has_consistent_priced_offering_value(filing):
        return False
    return True


def enforce_public_feed_policy(output_path):
    """Remove non-qualifying records, normalize safe fields, and sync the CSV."""
    output_path = Path(output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    # Make the pre-pricing quote guard part of the canonical release gate. This
    # protects every publisher that invokes public-feed policy even if a workflow
    # forgets to run the standalone sanitizer first. The sanitizer only removes
    # market-derived fields from non-424B4 rows; it never invents replacement data.
    payload, _ = sanitize_prepricing_quotes(payload)

    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("Public feed must contain a filings list")

    qualifying = []
    for filing in filings:
        if not isinstance(filing, dict):
            continue
        normalized = _sanitize_impossible_lifecycle_date(filing)
        if not _has_valid_filing_date(normalized) or not qualifies_for_public_feed(normalized):
            continue
        normalized = _remove_document_heading_people(normalized)
        normalized = _normalize_people_types(normalized)
        normalized = _normalize_person_ownership_metrics(normalized)
        normalized = _scrub_stanford_operational_errors(normalized)
        normalized = _normalize_market_value_consistency(normalized)
        qualifying.append(normalized)

    removed = len(filings) - len(qualifying)
    changed = qualifying != filings
    if changed:
        payload["filings"] = qualifying
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)
    write_dashboard_csv(payload.get("filings", []), output_path)
    return payload, removed


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../docs/data/filings.json")
    _, removed_count = enforce_public_feed_policy(target)
    print(f"Public-feed policy removed {removed_count} non-qualifying filing(s)")

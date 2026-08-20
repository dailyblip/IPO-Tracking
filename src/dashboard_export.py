"""Build the static JSON and CSV feeds consumed by the Research Monitor UI."""

from __future__ import annotations

import csv
import calendar
import json
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path

from prospect_research import prospect_person_metadata

SCHEMA_VERSION = 1
MAX_FILINGS = 250
PUBLIC_FILING_FIELDS = {
    "id", "company", "ticker", "cik", "accession_no", "form", "filed",
    "priority", "status", "value", "value_label", "people_count", "signals",
    "people", "sec_url", "stage", "price_range", "filing_price",
    "offering_price", "current_price", "price_updated", "location", "location_source",
    "primary_offering_shares", "secondary_offering_shares", "offering_size_source",
    "offering_size_confidence", "lockup_end_date",
    "lockup_duration_days", "lockup_duration_value", "lockup_duration_unit",
    "lockup_text", "lockup_scope", "lockup_terms", "lockup_confidence",
}
PUBLIC_PERSON_FIELDS = {
    "name", "shares", "cash_value", "stanford_university_bio", "ipo_value",
    "liquid_shares", "liquid_value", "locked_shares", "locked_value",
    "cash_realized_ipo", "liquidity_status", "liquidity_confidence",
    "holder_type", "role", "ownership_percent", "ownership_percent_before", "ownership_percent_after", "shares_before_ipo",
    "shares_sold_ipo", "shares_after_ipo", "stanford_source",
    "lockup_end_date", "lockup_scope", "lockup_duration_days", "lockup_duration_value",
    "lockup_duration_unit", "lockup_schedule", "lockup_text", "valuation_as_of",
}
CSV_FIELDS = (
    "company", "ticker", "cik", "accession_no", "form", "stage", "filed",
    "priority", "status", "offering_value", "primary_offering_shares", "secondary_offering_shares",
    "offering_size_source", "offering_size_confidence", "filing_price", "offering_price",
    "current_price", "price_updated", "location", "location_source", "lockup_end_date", "holder_name", "shares",
    "cash_value", "ipo_value", "liquid_shares", "liquid_value", "locked_shares",
    "locked_value", "cash_realized_ipo", "liquidity_status", "liquidity_confidence",
    "stanford_university_bio", "holder_type", "role", "ownership_percent", "ownership_percent_before", "ownership_percent_after",
    "shares_before_ipo", "shares_sold_ipo", "shares_after_ipo", "stanford_source",
    "lockup_scope", "valuation_as_of", "sec_url",
)


def _number(value):
    try:
        return float(str(value).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None


def _money(value):
    value = _number(value)
    if value is None or value <= 0:
        return "—"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def _boolean(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _clean_company_name(value):
    cleaned = re.sub(
        r"\s*\(CIK\s+\d+\)\s*$", "", str(value or ""), flags=re.IGNORECASE
    ).strip()
    return re.sub(
        r"\s+\([A-Z][A-Z0-9.-]{0,9}(?:,\s*[A-Z][A-Z0-9.-]{0,9})*\)\s*$",
        "",
        cleaned,
    ).strip()


def _clean_holder_name(value):
    raw = "".join(
        character
        for character in str(value or "")
        if unicodedata.category(character) != "Cf"
    )
    name = " ".join(raw.split())
    name = re.sub(r"\s*\.{3,}\s*$", "", name)
    name = re.sub(r"(?:\s*\(\d+[a-z]?\))+$", "", name, flags=re.I)
    name = re.sub(r"[†‡*]+$", "", name).strip()
    return name


def _holder_identity_key(value):
    return " ".join(_clean_holder_name(value).lower().split())


def _is_aggregate_holder(name):
    lowered = name.lower()
    return (
        "as a group" in lowered
        and "director" in lowered
        and "executive officer" in lowered
    )


def _public_only(filing):
    """Allowlist public output fields, including records from older feed versions."""
    clean = {key: value for key, value in filing.items() if key in PUBLIC_FILING_FIELDS}
    clean["people"] = [
        {key: value for key, value in person.items() if key in PUBLIC_PERSON_FIELDS}
        for person in filing.get("people", [])
        if isinstance(person, dict)
    ]
    return clean


def _priority(rows, people):
    amount = max((_number(row.get("Amount Raised")) or 0 for row in rows), default=0)
    largest_holding = max((person.get("cash_value") or 0 for person in people), default=0)
    if amount >= 500_000_000 or largest_holding >= 250_000_000:
        return "High"
    if amount >= 100_000_000 or largest_holding >= 50_000_000:
        return "Medium"
    return "Low"


def _add_duration(start_date, value, unit):
    if not start_date or value in (None, "") or not unit:
        return None
    try:
        base = datetime.fromisoformat(str(start_date)).date()
        value = int(value)
    except (TypeError, ValueError):
        return None
    unit = str(unit).lower()
    if unit == "days":
        return (base + timedelta(days=value)).isoformat()
    if unit == "months":
        month_index = base.month - 1 + value
        year = base.year + month_index // 12
        month = month_index % 12 + 1
        day = min(base.day, calendar.monthrange(year, month)[1])
        return base.replace(year=year, month=month, day=day).isoformat()
    if unit == "years":
        try:
            return base.replace(year=base.year + value).isoformat()
        except ValueError:
            return base.replace(month=2, day=28, year=base.year + value).isoformat()
    return None


def _parse_terms(value):
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _lockup_metadata(rows):
    text = next((str(row.get("Lock-Up Text") or "") for row in rows if row.get("Lock-Up Text")), "")
    value = next((row.get("Lock-Up Duration Value") for row in rows if row.get("Lock-Up Duration Value") not in (None, "")), None)
    unit = next((row.get("Lock-Up Duration Unit") for row in rows if row.get("Lock-Up Duration Unit")), None)
    days = next((row.get("Lock-Up Duration Days") for row in rows if row.get("Lock-Up Duration Days") not in (None, "")), None)
    scope = next((row.get("Lock-Up Scope") for row in rows if row.get("Lock-Up Scope")), None)
    tags_raw = next((row.get("Lock-Up Scope Tags") for row in rows if row.get("Lock-Up Scope Tags")), "")
    tags = [tag.strip() for tag in str(tags_raw).split(",") if tag.strip()]
    terms = _parse_terms(next((row.get("Lock-Up Terms JSON") for row in rows if row.get("Lock-Up Terms JSON")), "[]"))
    confidence = next((row.get("Lock-Up Confidence") for row in rows if row.get("Lock-Up Confidence")), None)

    # Backward compatibility for historical rows generated before structured fields.
    if not text:
        legacy = next((str(row.get("Lock-Up Expiry") or "") for row in rows if row.get("Lock-Up Expiry")), "")
        if legacy and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", legacy):
            text = legacy
    if value is None and text:
        match = re.search(r"(\d{2,3})\s+days", text, re.I)
        if match:
            value, unit, days = int(match.group(1)), "days", int(match.group(1))

    pricing = next((str(row.get("Date of Pricing") or "") for row in rows if row.get("Date of Pricing")), "")
    end = _add_duration(pricing, value, unit)
    enriched_terms = []
    for term in terms:
        if not isinstance(term, dict):
            continue
        item = dict(term)
        item["end_date"] = _add_duration(pricing, item.get("duration_value"), item.get("duration_unit"))
        enriched_terms.append(item)
    return {
        "text": text or None, "days": int(days) if str(days or "").isdigit() else None,
        "value": int(value) if str(value or "").isdigit() else value, "unit": unit,
        "scope": scope, "scope_tags": tags, "terms": enriched_terms,
        "confidence": confidence, "end": end,
    }


def _role_matches_scope(role, tags, shares_sold=None):
    role = str(role or "").lower()
    tags = set(tags or [])
    if tags & {"substantially_all_holders", "all_other_holders"}:
        return True
    if "directors" in tags and any(word in role for word in ("director", "chair")):
        return True
    if "executive_officers" in tags and any(word in role for word in ("chief", "president", "officer", "general counsel", "treasurer")):
        return True
    if "selling_stockholders" in tags and (_number(shares_sold) or 0) > 0:
        return True
    return False


def _applicable_lockup(lockup, name, metadata, row):
    """Return only lock-up terms defensibly applicable to this holder."""
    name_key = _holder_identity_key(name)
    all_terms = lockup.get("terms") or []
    special = []
    for term in all_terms:
        holder = term.get("special_holder")
        if not holder:
            continue
        holder_key = _holder_identity_key(holder)
        if holder_key in {name_key, name_key.replace("entities affiliated with ", "")}:
            special.append(term)
        elif holder_key and name_key and (holder_key in name_key or name_key in holder_key):
            special.append(term)
    if special:
        return {"terms": special, "special": True}

    matched = [
        term for term in all_terms
        if not term.get("special_holder")
        and _role_matches_scope(
            metadata.get("role"),
            term.get("scope_tags") or [],
            row.get("Shares Sold in IPO"),
        )
    ]
    if matched:
        return {"terms": matched, "special": False}

    # Legacy structured records may have only a filing-level primary term. Preserve
    # the schedule as evidence, but never invent holder coverage.
    if not all_terms and _role_matches_scope(
        metadata.get("role"), lockup.get("scope_tags"), row.get("Shares Sold in IPO")
    ) and lockup.get("value"):
        primary = {
            "duration_value": lockup.get("value"), "duration_unit": lockup.get("unit"),
            "duration_days": lockup.get("days"), "end_date": lockup.get("end"),
            "scope": lockup.get("scope"), "scope_tags": lockup.get("scope_tags"),
            "source_text": lockup.get("text"), "has_staggered_releases": False,
            "tranche_percent": None, "covers_full_position": False,
        }
        return {"terms": [primary], "special": False}
    return {"terms": [], "special": False}


def _as_of_date(value=None):
    if value:
        try:
            return datetime.fromisoformat(str(value)[:10]).date()
        except ValueError:
            pass
    return datetime.now(timezone.utc).date()


def _person_liquidity(shares, current_value, ipo_price, lockup, name, metadata, row, as_of_date=None):
    """Classify liquidity only when the filing supplies defensible quantities."""
    shares = _number(shares); current_value = _number(current_value); ipo_price = _number(ipo_price)
    ipo_value = shares * ipo_price if shares is not None and ipo_price else None
    base = {"ipo_value": ipo_value, "cash_realized_ipo": None}
    if shares is None:
        return {**base, "liquid_shares": None, "liquid_value": None, "locked_shares": None, "locked_value": None, "liquidity_status": "Unknown", "liquidity_confidence": "Unknown — share count unavailable", "lockup_schedule": []}

    applicable = _applicable_lockup(lockup, name, metadata, row)
    terms = applicable.get("terms") or []
    schedule = [
        {k: term.get(k) for k in (
            "duration_value", "duration_unit", "end_date", "scope", "special_holder",
            "source_text", "has_staggered_releases", "tranche_percent",
            "tranche_label", "covers_full_position",
        )}
        for term in terms if term.get("duration_value")
    ]
    if not schedule:
        return {**base, "liquid_shares": None, "liquid_value": None, "locked_shares": None, "locked_value": None, "liquidity_status": "Unclassified", "liquidity_confidence": "Unknown — filing has no defensible holder-specific lock-up mapping", "lockup_schedule": []}

    end_dates = [item.get("end_date") for item in schedule if item.get("end_date")]
    final_end = max(end_dates) if end_dates else None
    today = _as_of_date(as_of_date or row.get("Last Updated"))

    # Explicit percentages are the gold-standard case: they let us translate the
    # prospectus schedule into currently locked/liquid shares without guessing.
    percentages = []
    for item in schedule:
        pct = _number(item.get("tranche_percent"))
        if pct is None:
            percentages = []
            break
        percentages.append(pct)
    pct_total = sum(percentages) if percentages else None
    if percentages and abs(pct_total - 100.0) <= 0.05 and all(item.get("end_date") for item in schedule):
        active_pct = 0.0
        for item, pct in zip(schedule, percentages):
            try:
                end_date = datetime.fromisoformat(str(item.get("end_date"))[:10]).date()
            except ValueError:
                percentages = []
                break
            if end_date > today:
                active_pct += pct
        if percentages:
            active_pct = max(0.0, min(100.0, active_pct))
            locked_shares = round(shares * active_pct / 100.0)
            liquid_shares = shares - locked_shares
            locked_value = current_value * active_pct / 100.0 if current_value is not None else None
            liquid_value = current_value - locked_value if current_value is not None else None
            if active_pct <= 0.05:
                status = "Staggered lock-up expired"
            elif active_pct >= 99.95:
                status = "Staggered lock-up — 100% currently restricted"
            else:
                status = f"Staggered lock-up — {active_pct:g}% currently restricted"
            return {**base, "liquid_shares": liquid_shares, "liquid_value": liquid_value, "locked_shares": locked_shares, "locked_value": locked_value, "liquidity_status": status, "liquidity_confidence": "High — current restricted percentage derived from explicit prospectus tranches; disclosed exceptions or underwriter waivers may apply", "lockup_schedule": schedule, "lockup_end_date": final_end}

    # A single term can support a whole-position classification only when the source
    # explicitly says it covers the full disclosed position. Role membership alone is
    # not enough: Rule 701/award-specific clauses often cover only a subset of shares.
    if len(schedule) == 1 and schedule[0].get("covers_full_position") and schedule[0].get("end_date"):
        try:
            end_date = datetime.fromisoformat(str(schedule[0]["end_date"])[:10]).date()
            active = end_date > today
        except ValueError:
            active = None
        if active is not None:
            return {**base, "liquid_shares": 0 if active else shares, "liquid_value": 0 if active else current_value, "locked_shares": shares if active else 0, "locked_value": current_value if active else 0, "liquidity_status": "Locked" if active else "Lock-up expired", "liquidity_confidence": "High — prospectus expressly maps the full covered position; disclosed exceptions or underwriter waivers may apply", "lockup_schedule": schedule, "lockup_end_date": final_end}

    staged = len(schedule) > 1 or any(item.get("has_staggered_releases") for item in schedule)
    if staged:
        return {**base, "liquid_shares": None, "liquid_value": None, "locked_shares": None, "locked_value": None, "liquidity_status": "Staggered lock-up — tranche quantities unresolved", "liquidity_confidence": "Lock-up schedule found, but the filing does not support a complete quantitative allocation", "lockup_schedule": schedule, "lockup_end_date": final_end}

    return {**base, "liquid_shares": None, "liquid_value": None, "locked_shares": None, "locked_value": None, "liquidity_status": "Lock-up applies — covered quantity unresolved", "liquidity_confidence": "Holder class is supported, but the filing does not establish that the entire disclosed position is covered", "lockup_schedule": schedule, "lockup_end_date": final_end}


def _signals(rows, people):
    signals = []
    amount = max((_number(row.get("Amount Raised")) or 0 for row in rows), default=0)
    largest_holding = max((person.get("cash_value") or 0 for person in people), default=0)
    lockup = next((row.get("Lock-Up Text") for row in rows if row.get("Lock-Up Text")), None) or next((row.get("Lock-Up Terms JSON") for row in rows if row.get("Lock-Up Terms JSON") not in (None, "", "[]")), None)

    if people:
        signals.append(
            f"{len(people)} named beneficial owner{'s' if len(people) != 1 else ''} disclosed"
        )
    else:
        signals.append("Final prospectus available for researcher review")
    if amount:
        signals.append(f"Offering raised approximately {_money(amount)}")
    if largest_holding:
        signals.append(f"Largest named holding currently valued at approximately {_money(largest_holding)}")
    if lockup:
        signals.append("Lock-up terms captured for liquidity-event follow-up")
    return signals or ["New final prospectus available for researcher review"]


def build_payload(rows, generated_at=None):
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    grouped = {}
    for row in rows:
        accession = row.get("_accession_no", "")
        key = accession or "|".join(
            str(row.get(field, "")) for field in ("Ticker", "Date of Pricing", "Company Name")
        )
        grouped.setdefault(key, []).append(row)

    filings = []
    for key, group in grouped.items():
        first = group[0]
        amount = max((_number(row.get("Amount Raised")) or 0 for row in group), default=0)
        lockup = _lockup_metadata(group)
        people = []
        seen = set()
        for row in group:
            name = _clean_holder_name(row.get("Holder Name", ""))
            identity_key = _holder_identity_key(name)
            if not name or _is_aggregate_holder(name) or identity_key in seen:
                continue
            seen.add(identity_key)
            shares = _number(row.get("Shares After IPO"))
            if shares is None:
                shares = _number(row.get("Shares"))
            cash_value = _number(row.get("Cash Value"))
            metadata = prospect_person_metadata(row, name)
            liquidity = _person_liquidity(shares, cash_value, _number(first.get("Actual Price")), lockup, name, metadata, row)
            realized = _number(row.get("Cash Realized IPO"))
            if realized is not None:
                liquidity["cash_realized_ipo"] = realized
            person_lockup_end = liquidity.get("lockup_end_date")
            people.append({"name": name, "shares": shares, "cash_value": cash_value, "stanford_university_bio": _boolean(row.get("Stanford University in Bio")), "lockup_end_date": person_lockup_end, "lockup_scope": "holder-mapped" if person_lockup_end or liquidity.get("lockup_schedule") else ("filing-level-unmapped" if lockup.get("text") else None), "lockup_duration_days": lockup.get("days"), "lockup_duration_value": lockup.get("value"), "lockup_duration_unit": lockup.get("unit"), "lockup_text": lockup.get("text"), "valuation_as_of": first.get("Last Updated") or None, **metadata, **liquidity})

        filings.append({
            "id": key,
            "company": _clean_company_name(first.get("Company Name", "Unknown")),
            "ticker": first.get("Ticker", ""),
            "cik": str(first.get("_cik", "")).zfill(10) if first.get("_cik") else "",
            "accession_no": first.get("_accession_no", ""),
            "form": first.get("_form") or "424B4",
            "filed": first.get("Date of Pricing") or first.get("Date of Filing") or "",
            "stage": "Priced",
            "priority": _priority(group, people),
            "status": "New",
            "value": amount or None,
            "value_label": _money(amount),
            "primary_offering_shares": _number(first.get("Primary Offering Shares")),
            "secondary_offering_shares": _number(first.get("Secondary Offering Shares")),
            "offering_size_source": first.get("Offering Size Source") or None,
            "offering_size_confidence": first.get("Offering Size Confidence") or None,
            "filing_price": first.get("Filing Price") or None,
            "offering_price": _number(first.get("Actual Price")),
            "current_price": _number(first.get("Current Price")),
            "price_updated": first.get("Last Updated") or None,
            "location": first.get("Location") or None,
            "location_source": first.get("Location Source") or None,
            "lockup_end_date": lockup.get("end"),
            "lockup_duration_days": lockup.get("days"),
            "lockup_duration_value": lockup.get("value"),
            "lockup_duration_unit": lockup.get("unit"),
            "lockup_text": lockup.get("text"),
            "lockup_scope": lockup.get("scope"),
            "lockup_terms": lockup.get("terms"),
            "lockup_confidence": lockup.get("confidence"),
            "people_count": len(people),
            "signals": _signals(group, people),
            "people": people,
            "sec_url": first.get("_sec_url", "https://www.sec.gov/edgar/search/"),
        })

    filings.sort(key=lambda filing: (filing.get("filed", ""), filing.get("company", "")), reverse=True)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source": "SEC EDGAR",
        "filings": filings,
    }


def _csv_rows(filings):
    """Flatten one filing per holder; preserve filing-only rows when no owner was parsed."""
    for filing in filings:
        people = filing.get("people") or [None]
        for person in people:
            person = person or {}
            yield {
                "company": filing.get("company", ""),
                "ticker": filing.get("ticker", ""),
                "cik": filing.get("cik", ""),
                "accession_no": filing.get("accession_no", ""),
                "form": filing.get("form", ""),
                "stage": filing.get("stage", ""),
                "filed": filing.get("filed", ""),
                "priority": filing.get("priority", ""),
                "status": filing.get("status", ""),
                "offering_value": filing.get("value"),
                "primary_offering_shares": filing.get("primary_offering_shares"),
                "secondary_offering_shares": filing.get("secondary_offering_shares"),
                "offering_size_source": filing.get("offering_size_source"),
                "offering_size_confidence": filing.get("offering_size_confidence"),
                "filing_price": filing.get("price_range") or filing.get("filing_price"),
                "offering_price": filing.get("offering_price"),
                "current_price": filing.get("current_price"),
                "price_updated": filing.get("price_updated"),
                "location": filing.get("location"),
                "location_source": filing.get("location_source"),
                "lockup_end_date": filing.get("lockup_end_date"),
                "holder_name": person.get("name", ""),
                "shares": person.get("shares"), "cash_value": person.get("cash_value"),
                "ipo_value": person.get("ipo_value"), "liquid_shares": person.get("liquid_shares"),
                "liquid_value": person.get("liquid_value"), "locked_shares": person.get("locked_shares"),
                "locked_value": person.get("locked_value"), "cash_realized_ipo": person.get("cash_realized_ipo"),
                "liquidity_status": person.get("liquidity_status"), "liquidity_confidence": person.get("liquidity_confidence"),
                "stanford_university_bio": person.get("stanford_university_bio", False),
                "holder_type": person.get("holder_type"), "role": person.get("role"),
                "ownership_percent": person.get("ownership_percent"), "ownership_percent_before": person.get("ownership_percent_before"), "ownership_percent_after": person.get("ownership_percent_after"),
                "shares_before_ipo": person.get("shares_before_ipo"),
                "shares_sold_ipo": person.get("shares_sold_ipo"), "shares_after_ipo": person.get("shares_after_ipo"),
                "stanford_source": person.get("stanford_source"), "lockup_scope": person.get("lockup_scope"),
                "valuation_as_of": person.get("valuation_as_of"),
                "sec_url": filing.get("sec_url", ""),
            }


def _write_csv(filings, output_path):
    csv_path = output_path.with_suffix(".csv")
    temporary = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(_csv_rows(filings))
    temporary.replace(csv_path)
    return csv_path


def write_dashboard_csv(filings, output_path):
    """Write the flattened CSV companion for an already-built public feed."""
    return _write_csv(filings, Path(output_path))


def refresh_market_prices(output_path, market_prices, updated_at=None):
    """Refresh delayed quotes and holder cash values in the public feed."""
    output_path = Path(output_path)
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    updated_at = updated_at or datetime.now(timezone.utc).isoformat()
    changed = False
    for filing in payload.get("filings", []):
        ticker = str(filing.get("ticker") or "").strip().upper()
        price = _number(market_prices.get(ticker)) if ticker else None
        if price is None or price <= 0:
            continue
        filing["current_price"] = price
        filing["price_updated"] = updated_at
        for person in filing.get("people", []):
            shares = _number(person.get("shares"))
            if shares is not None:
                person["cash_value"] = shares * price
                if _number(person.get("liquid_shares")) is not None: person["liquid_value"] = _number(person.get("liquid_shares")) * price
                if _number(person.get("locked_shares")) is not None: person["locked_value"] = _number(person.get("locked_shares")) * price
        changed = True

    if changed:
        payload["generated_at"] = updated_at
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)
        _write_csv(payload.get("filings", []), output_path)
    return payload


def export_dashboard(rows, output_path, replace_start=None, replace_end=None):
    """
    Write the public JSON and flattened CSV feeds atomically.

    Daily runs merge into history. An explicit backfill range replaces existing
    records in that range first, so corrected eligibility rules can remove stale
    records instead of leaving them cached forever.
    """
    output_path = Path(output_path)
    current = build_payload(rows)
    existing = []
    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8")).get("filings", [])
        except (json.JSONDecodeError, OSError):
            existing = []

    if replace_start:
        upper_bound = replace_end or "9999-12-31"
        existing = [
            filing
            for filing in existing
            if not (
                isinstance(filing, dict)
                and str(filing.get("form") or "424B4").upper() == "424B4"
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(filing.get("filed", "")))
                and replace_start <= filing["filed"] <= upper_bound
            )
        ]

    merged = {
        filing["id"]: _public_only(filing)
        for filing in existing
        if isinstance(filing, dict) and filing.get("id")
    }
    merged.update({filing["id"]: _public_only(filing) for filing in current["filings"]})
    current["filings"] = sorted(
        merged.values(), key=lambda filing: (filing.get("filed", ""), filing.get("company", "")), reverse=True
    )[:MAX_FILINGS]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(output_path)
    _write_csv(current["filings"], output_path)
    return current

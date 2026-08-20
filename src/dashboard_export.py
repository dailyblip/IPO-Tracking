"""Build the static JSON and CSV feeds consumed by the Research Monitor UI."""

from __future__ import annotations

import csv
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
    "offering_price", "current_price", "price_updated", "lockup_end_date",
    "lockup_duration_days", "lockup_text",
}
PUBLIC_PERSON_FIELDS = {
    "name", "shares", "cash_value", "stanford_university_bio", "ipo_value",
    "liquid_shares", "liquid_value", "locked_shares", "locked_value",
    "cash_realized_ipo", "liquidity_status", "liquidity_confidence",
    "holder_type", "role", "ownership_percent", "ownership_percent_before", "ownership_percent_after", "shares_before_ipo",
    "shares_sold_ipo", "shares_after_ipo", "stanford_source",
    "lockup_end_date", "lockup_scope", "valuation_as_of",
}
CSV_FIELDS = (
    "company", "ticker", "cik", "accession_no", "form", "stage", "filed",
    "priority", "status", "offering_value", "filing_price", "offering_price",
    "current_price", "price_updated", "lockup_end_date", "holder_name", "shares",
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
    return re.sub(r"(?:\s*\(\d+\))+$", "", name).strip()


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


def _lockup_metadata(rows):
    raw = next((str(row.get("Lock-Up Expiry") or "") for row in rows if row.get("Lock-Up Expiry")), "")
    match = re.search(r"(\d{2,3})\s+days", raw, re.IGNORECASE)
    days = int(match.group(1)) if match else None
    pricing = next((str(row.get("Date of Pricing") or "") for row in rows if row.get("Date of Pricing")), "")
    end = None
    if days and re.fullmatch(r"\d{4}-\d{2}-\d{2}", pricing):
        try:
            end = (datetime.fromisoformat(pricing).date() + timedelta(days=days)).isoformat()
        except ValueError:
            pass
    return {"text": raw or None, "days": days, "end": end}


def _person_liquidity(shares, current_value, ipo_price, lockup):
    shares = _number(shares); current_value = _number(current_value); ipo_price = _number(ipo_price)
    ipo_value = shares * ipo_price if shares is not None and ipo_price else None
    if shares is None:
        return {"ipo_value": ipo_value, "liquid_shares": None, "liquid_value": None, "locked_shares": None, "locked_value": None, "cash_realized_ipo": None, "liquidity_status": "Unknown", "liquidity_confidence": "Unknown — share count unavailable"}
    if lockup.get("end"):
        try:
            active = datetime.fromisoformat(lockup["end"]).date() > datetime.now(timezone.utc).date()
        except ValueError:
            active = False
        return {"ipo_value": ipo_value, "liquid_shares": 0 if active else shares, "liquid_value": 0 if active else current_value, "locked_shares": shares if active else 0, "locked_value": current_value if active else 0, "cash_realized_ipo": None, "liquidity_status": "Locked" if active else "Lock-up expired", "liquidity_confidence": "Estimated from filing-level lock-up; individual exemptions may apply"}
    return {"ipo_value": ipo_value, "liquid_shares": None, "liquid_value": None, "locked_shares": None, "locked_value": None, "cash_realized_ipo": None, "liquidity_status": "Unclassified", "liquidity_confidence": "Unknown — lock-up coverage not structured"}


def _signals(rows, people):
    signals = []
    amount = max((_number(row.get("Amount Raised")) or 0 for row in rows), default=0)
    largest_holding = max((person.get("cash_value") or 0 for person in people), default=0)
    lockup = next((row.get("Lock-Up Expiry") for row in rows if row.get("Lock-Up Expiry")), None)

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
            if not name or _is_aggregate_holder(name) or name.lower() in seen:
                continue
            seen.add(name.lower())
            shares = _number(row.get("Shares")); cash_value = _number(row.get("Cash Value"))
            liquidity = _person_liquidity(shares, cash_value, _number(first.get("Actual Price")), lockup)
            metadata = prospect_person_metadata(row, name)
            realized = _number(row.get("Cash Realized IPO"))
            if realized is not None:
                liquidity["cash_realized_ipo"] = realized
            realized = _number(row.get("Cash Realized IPO"))
            if realized is not None:
                liquidity["cash_realized_ipo"] = realized
            people.append({"name": name, "shares": shares, "cash_value": cash_value, "stanford_university_bio": _boolean(row.get("Stanford University in Bio")), "lockup_end_date": lockup.get("end"), "lockup_scope": "filing-level" if lockup.get("text") else None, "valuation_as_of": first.get("Last Updated") or None, **metadata, **liquidity})

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
            "filing_price": first.get("Filing Price") or None,
            "offering_price": _number(first.get("Actual Price")),
            "current_price": _number(first.get("Current Price")),
            "price_updated": first.get("Last Updated") or None,
            "lockup_end_date": lockup.get("end"),
            "lockup_duration_days": lockup.get("days"),
            "lockup_text": lockup.get("text"),
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
                "filing_price": filing.get("price_range") or filing.get("filing_price"),
                "offering_price": filing.get("offering_price"),
                "current_price": filing.get("current_price"),
                "price_updated": filing.get("price_updated"),
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

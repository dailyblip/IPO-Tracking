"""Build the static JSON feed consumed by the Research Monitor UI."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
MAX_FILINGS = 250
PUBLIC_FILING_FIELDS = {
    "id", "company", "ticker", "cik", "accession_no", "form", "filed",
    "priority", "status", "value", "value_label", "people_count", "signals",
    "people", "sec_url", "stage", "price_range", "filing_price",
    "offering_price", "current_price", "price_updated",
}
PUBLIC_PERSON_FIELDS = {
    "name", "shares", "cash_value", "stanford_university_bio",
}


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
        people = []
        seen = set()
        for row in group:
            name = _clean_holder_name(row.get("Holder Name", ""))
            if not name or _is_aggregate_holder(name) or name.lower() in seen:
                continue
            seen.add(name.lower())
            people.append({
                "name": name,
                "shares": _number(row.get("Shares")),
                "cash_value": _number(row.get("Cash Value")),
                "stanford_university_bio": _boolean(
                    row.get("Stanford University in Bio")
                ),
            })

        filings.append({
            "id": key,
            "company": _clean_company_name(first.get("Company Name", "Unknown")),
            "ticker": first.get("Ticker", ""),
            "cik": str(first.get("_cik", "")).zfill(10) if first.get("_cik") else "",
            "accession_no": first.get("_accession_no", ""),
            "form": first.get("_form") or "424B4",
            "filed": first.get("Date of Pricing") or first.get("Date of Filing") or "",
            "priority": _priority(group, people),
            "status": "New",
            "value": amount or None,
            "value_label": _money(amount),
            "filing_price": first.get("Filing Price") or None,
            "offering_price": _number(first.get("Actual Price")),
            "current_price": _number(first.get("Current Price")),
            "price_updated": first.get("Last Updated") or None,
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
        changed = True

    if changed:
        payload["generated_at"] = updated_at
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)
    return payload


def export_dashboard(rows, output_path, replace_start=None, replace_end=None):
    """
    Write the public feed atomically.

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
    return current

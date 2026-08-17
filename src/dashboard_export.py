"""Build the static JSON feed consumed by the Research Monitor UI."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
MAX_FILINGS = 250


def _number(value):
    try:
        return float(str(value).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None


def _money(value):
    value = _number(value)
    if value is None:
        return "—"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def _priority(rows):
    max_grade = max((_number(row.get("Stanford Grade")) or 0 for row in rows), default=0)
    amount = max((_number(row.get("Amount Raised")) or 0 for row in rows), default=0)
    if max_grade >= 4 or amount >= 500_000_000:
        return "High"
    if max_grade >= 2 or amount >= 100_000_000:
        return "Medium"
    return "Low"


def _signals(rows):
    signals = []
    strong = sum(1 for row in rows if (_number(row.get("Stanford Grade")) or 0) >= 4)
    possible = sum(1 for row in rows if 1 <= (_number(row.get("Stanford Grade")) or 0) < 4)
    amount = max((_number(row.get("Amount Raised")) or 0 for row in rows), default=0)
    holdings = sum((_number(row.get("Cash Value")) or 0 for row in rows))
    flagged = sum(1 for row in rows if row.get("QC Status") == "Needs Review")
    lockup = next((row.get("Lock-Up Expiry") for row in rows if row.get("Lock-Up Expiry")), None)

    if strong:
        signals.append(f"{strong} holder{'s' if strong != 1 else ''} with strong Stanford affiliation evidence")
    if possible:
        signals.append(f"{possible} additional affiliation signal{'s' if possible != 1 else ''} for researcher review")
    if amount:
        signals.append(f"Offering raised approximately {_money(amount)}")
    if holdings:
        signals.append(f"Named holdings currently valued at approximately {_money(holdings)}")
    if lockup:
        signals.append("Lock-up terms captured for liquidity-event follow-up")
    if flagged:
        signals.append(f"{flagged} extracted record{'s' if flagged != 1 else ''} need data-quality review")
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
            name = str(row.get("Holder Name", "")).strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            people.append({
                "name": name,
                "shares": _number(row.get("Shares")),
                "cash_value": _number(row.get("Cash Value")),
                "stanford_grade": int(_number(row.get("Stanford Grade")) or 0),
                "affiliation_evidence": row.get("Stanford Justification", ""),
                "qc_status": row.get("QC Status", ""),
                "qc_notes": row.get("QC Notes", ""),
            })

        filings.append({
            "id": key,
            "company": first.get("Company Name", "Unknown"),
            "ticker": first.get("Ticker", ""),
            "cik": str(first.get("_cik", "")).zfill(10) if first.get("_cik") else "",
            "accession_no": first.get("_accession_no", ""),
            "form": first.get("_form", "424B4"),
            "filed": first.get("Date of Pricing") or first.get("Date of Filing") or "",
            "priority": _priority(group),
            "status": "New",
            "value": amount or None,
            "value_label": _money(amount),
            "people_count": len(people),
            "signals": _signals(group),
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


def export_dashboard(rows, output_path):
    """Merge this run into the historical static feed and write atomically."""
    output_path = Path(output_path)
    current = build_payload(rows)
    existing = []
    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8")).get("filings", [])
        except (json.JSONDecodeError, OSError):
            existing = []

    merged = {filing["id"]: filing for filing in existing if filing.get("id")}
    merged.update({filing["id"]: filing for filing in current["filings"]})
    current["filings"] = sorted(
        merged.values(), key=lambda filing: (filing.get("filed", ""), filing.get("company", "")), reverse=True
    )[:MAX_FILINGS]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(output_path)
    return current


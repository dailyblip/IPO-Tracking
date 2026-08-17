"""Build a forward-looking feed of recent domestic IPO registration statements.

This complements the priced-IPO 424B4 pipeline. It watches S-1 and S-1/A
filings before pricing, filters obvious non-IPO records, captures a preliminary
price range when one is available, and writes both a dedicated S-1 history and
normalized records into the main Research Monitor queue.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import date, timedelta, timezone, datetime
from pathlib import Path

import requests

import edgar_client
import filing_parser

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "s1_watch.json"
QUEUE_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"
MAX_RECORDS = 250
FORM_TYPES = {"S-1", "S-1/A"}


def _headers() -> dict:
    user_agent = os.environ.get("SEC_EDGAR_USER_AGENT")
    if not user_agent:
        raise RuntimeError("SEC_EDGAR_USER_AGENT environment variable is not set.")
    return {"User-Agent": user_agent}


def _clean_company_name(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def parse_daily_index(text: str) -> list[dict]:
    """Parse S-1/S-1A records from an SEC daily master index."""
    records = []
    in_records = False
    for line in str(text or "").splitlines():
        if line.startswith("-----"):
            in_records = True
            continue
        if not in_records:
            continue
        parts = line.split("|")
        if len(parts) != 5:
            continue
        cik, company_name, form_type, filing_date, filename = parts
        form_type = form_type.strip().upper()
        if form_type not in FORM_TYPES:
            continue
        accession_no = filename.rsplit("/", 1)[-1].removesuffix(".txt")
        records.append({
            "company_name": _clean_company_name(company_name),
            "cik": cik.strip(),
            "form_type": form_type,
            "filing_date": filing_date.strip(),
            "accession_no": accession_no,
        })
    return records


def discover_recent_s1(days_back: int = 4, today: date | None = None) -> list[dict]:
    """Discover recent S-1/S-1A filings using SEC daily master indexes."""
    today = today or date.today()
    start = today - timedelta(days=max(1, days_back))
    headers = _headers()
    found = []
    seen = set()

    current = start
    while current <= today:
        quarter = ((current.month - 1) // 3) + 1
        url = (
            f"https://www.sec.gov/Archives/edgar/daily-index/{current.year}/"
            f"QTR{quarter}/master.{current.strftime('%Y%m%d')}.idx"
        )
        try:
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code == 404:
                current += timedelta(days=1)
                continue
            response.raise_for_status()
            time.sleep(edgar_client.REQUEST_DELAY_SECONDS)
        except requests.exceptions.RequestException as error:
            print(f"[s1_monitor] Daily index unavailable for {current}: {error}")
            current += timedelta(days=1)
            continue

        for record in parse_daily_index(response.text):
            if record["accession_no"] in seen:
                continue
            seen.add(record["accession_no"])
            found.append(record)
        current += timedelta(days=1)

    return found


def _format_range(low, high) -> str | None:
    try:
        low = float(low)
        high = float(high)
    except (TypeError, ValueError):
        return None
    if low <= 0 or high <= 0:
        return None
    return f"${low:,.2f}–${high:,.2f}"


def enrich_record(meta: dict) -> dict | None:
    """Validate an S-1 candidate and capture lightweight IPO-stage signals."""
    cik = meta.get("cik")
    company = meta.get("company_name") or "Unknown"
    form = meta.get("form_type") or "S-1"

    try:
        if not edgar_client.is_us_based(cik):
            return None
        if not edgar_client.is_first_time_registrant(cik):
            return None

        index_url = edgar_client.build_filing_index_url(cik, meta["accession_no"])
        document_url = filing_parser.find_primary_document_url(
            index_url, expected_form_types=["S-1", "S-1/A"]
        )
        soup = filing_parser.fetch_document(document_url)
        filing_text = soup.get_text(" ", strip=True)
        if edgar_client.check_spac_indicators(filing_text, company_name=company):
            return None
        if edgar_client.check_direct_listing_indicators(filing_text):
            return None

        parsed = filing_parser.parse_filing(document_url, is_range_filing=True)
        price_range = parsed.get("price_range", {})
        range_label = _format_range(price_range.get("range_low"), price_range.get("range_high"))

        ticker = None
        try:
            ticker = edgar_client.get_primary_ticker(cik)
        except Exception as error:
            print(f"[s1_monitor] Ticker lookup failed for {company}: {error}")

        signals = []
        if form == "S-1":
            signals.append("Initial registration statement filed — IPO is pre-pricing")
        else:
            signals.append("Registration statement amended — IPO remains pre-pricing")
        if range_label:
            signals.append(f"Preliminary offering range disclosed at {range_label}")
        else:
            signals.append("No preliminary price range detected yet")

        return {
            "id": meta["accession_no"],
            "company": company,
            "ticker": ticker or "",
            "cik": str(cik).zfill(10) if cik else "",
            "accession_no": meta["accession_no"],
            "form": form,
            "filed": meta.get("filing_date") or "",
            "stage": "Pre-pricing",
            "priority": "High" if range_label else "Medium",
            "price_range": range_label,
            "signals": signals,
            "sec_url": index_url,
        }
    except Exception as error:
        print(f"[s1_monitor] Skipping {company}: {error}")
        return None


def build_payload(records: list[dict], generated_at: str | None = None) -> dict:
    return {
        "schema_version": 1,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "source": "SEC EDGAR",
        "filings": sorted(
            records,
            key=lambda item: (item.get("filed", ""), item.get("company", "")),
            reverse=True,
        ),
    }


def export_feed(records: list[dict], output_path: Path = OUTPUT_PATH) -> dict:
    """Merge new records into bounded S-1 history and write atomically."""
    output_path = Path(output_path)
    existing = []
    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8")).get("filings", [])
        except (OSError, json.JSONDecodeError):
            existing = []

    merged = {
        item.get("id"): item
        for item in existing
        if isinstance(item, dict) and item.get("id")
    }
    merged.update({item["id"]: item for item in records if item.get("id")})
    payload = build_payload(list(merged.values()))
    payload["filings"] = payload["filings"][:MAX_RECORDS]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp = output_path.with_suffix(output_path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(output_path)
    return payload


def _queue_record(record: dict) -> dict:
    """Normalize a pre-pricing record to the existing dashboard schema."""
    cik = str(record.get("cik") or "").zfill(10) if record.get("cik") else ""
    return {
        # One live pre-pricing queue row per issuer; later amendments replace it.
        "id": f"s1:{cik or record.get('company', '')}",
        "company": record.get("company") or "Unknown",
        "ticker": record.get("ticker") or "",
        "cik": cik,
        "accession_no": record.get("accession_no") or record.get("id") or "",
        "form": record.get("form") or "S-1",
        "filed": record.get("filed") or "",
        "priority": record.get("priority") or "Medium",
        "status": "New",
        "value": None,
        "value_label": "—",
        "people_count": 0,
        "signals": list(record.get("signals") or []),
        "people": [],
        "sec_url": record.get("sec_url") or "https://www.sec.gov/edgar/search/",
    }


def sync_research_queue(records: list[dict], queue_path: Path = QUEUE_PATH) -> dict:
    """Merge current S-1 signals into the main researcher queue atomically.

    Existing priced records stay authoritative. If a 424B4 for the same CIK is
    already present, its pre-pricing queue row is removed rather than duplicated.
    """
    queue_path = Path(queue_path)
    existing = []
    if queue_path.exists():
        try:
            existing = json.loads(queue_path.read_text(encoding="utf-8")).get("filings", [])
        except (OSError, json.JSONDecodeError):
            existing = []

    priced_ciks = {
        str(item.get("cik") or "").zfill(10)
        for item in existing
        if isinstance(item, dict)
        and str(item.get("form") or "").upper() == "424B4"
        and item.get("cik")
    }

    merged = {
        item["id"]: item
        for item in existing
        if isinstance(item, dict)
        and item.get("id")
        and not (
            str(item.get("id", "")).startswith("s1:")
            and str(item.get("cik") or "").zfill(10) in priced_ciks
        )
    }

    for record in records:
        queue_record = _queue_record(record)
        if queue_record["cik"] and queue_record["cik"] in priced_ciks:
            merged.pop(queue_record["id"], None)
            continue
        merged[queue_record["id"]] = queue_record

    payload = build_payload(list(merged.values()))
    payload["filings"] = payload["filings"][:MAX_RECORDS]

    queue_path.parent.mkdir(parents=True, exist_ok=True)
    temp = queue_path.with_suffix(queue_path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(queue_path)
    return payload


def run(days_back: int = 4) -> dict:
    candidates = discover_recent_s1(days_back=days_back)
    print(f"[s1_monitor] Found {len(candidates)} recent S-1/S-1A filing(s).")
    records = []
    for index, meta in enumerate(candidates, 1):
        print(f"[s1_monitor] Processing {index}/{len(candidates)}: {meta['company_name']} ({meta['form_type']})")
        record = enrich_record(meta)
        if record:
            records.append(record)
    payload = export_feed(records)
    queue = sync_research_queue(records)
    print(f"[s1_monitor] Feed now contains {len(payload['filings'])} pre-pricing filing(s).")
    print(f"[s1_monitor] Research queue now contains {len(queue['filings'])} filing(s).")
    return payload


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SEC Research Monitor pre-pricing S-1 watcher")
    parser.add_argument("days_back", nargs="?", type=int, default=4)
    args = parser.parse_args()
    run(args.days_back)

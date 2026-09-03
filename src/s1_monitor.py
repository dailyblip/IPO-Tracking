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

from dashboard_export import write_dashboard_csv
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


def _normalize_filing_date(value: str) -> str:
    raw = str(value or "").strip()
    if re.fullmatch(r"\d{8}", raw):
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw


def _format_fixed_price(value) -> str | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return f"${value:,.2f}"


def _is_micro_self_underwritten_offering(filing_text: str, parsed: dict, ipo_size) -> bool:
    """Identify the narrow micro self-underwritten/no-exchange non-IPO pattern.

    The Any-size policy removes the old $100M publication threshold, but it does
    not turn every Securities Act registration into a qualifying IPO. A tiny
    self-underwritten, best-efforts offering with no exchange listing is the
    established non-listing public-offering pattern this detector was created to
    reject. A small IPO with an actual exchange listing remains eligible.
    """
    try:
        amount = float(ipo_size or 0)
    except (TypeError, ValueError):
        amount = 0
    if not (0 < amount < 1_000_000):
        return False
    text = " ".join(str(filing_text or "").lower().split())[:80000]
    self_sold = (
        "self-underwritten" in text
        or "self underwritten" in text
        or "best-efforts basis" in text
        or "best efforts basis" in text
    )
    cover = parsed.get("cover_page", {}) if isinstance(parsed, dict) else {}
    exchange = str(cover.get("exchange") or "").strip()
    return self_sold and not exchange


def _explicit_fixed_price_primary_terms(filing_text: str) -> dict:
    """Recover tightly anchored fixed-price primary IPO terms from the cover page.

    This fallback exists for micro/small issuer prospectuses whose SEC HTML says,
    for example, "We are offering for sale a total of 6,000,000 shares ... at a
    fixed price of $0.02 per share" but whose table markup defeats the generic
    cover parser. It intentionally does not use fee-table values or generic
    per-share amounts.
    """
    text = " ".join(str(filing_text or "").split())[:100000]
    pattern = re.compile(
        r"\bwe\s+are\s+offering\s+for\s+sale\s+(?:a\s+total\s+of\s+)?"
        r"([\d,]{2,})\s+shares\b"
        r"(?P<context>.{0,1200}?)"
        r"\bat\s+a\s+fixed\s+price\s+of\s+\$\s*(\d{1,4}(?:\.\d{1,4})?)"
        r"\s+per\s+share\b",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return {}

    context = match.group("context")
    # Do not flatten a mixed primary/secondary deal into an issuer-only total.
    if re.search(r"\bselling\s+(?:stockholder|shareholder)s?\b", context, re.IGNORECASE):
        return {}

    try:
        shares = int(match.group(1).replace(",", ""))
        price = float(match.group(3))
    except (TypeError, ValueError):
        return {}
    if shares <= 0 or price <= 0:
        return {}
    return {
        "shares": shares,
        "price": price,
        "source": "SEC cover: explicit fixed-price primary offering",
        "confidence": "High",
    }


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
            "filing_date": _normalize_filing_date(filing_date),
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


def _extract_ipo_size(filing_text: str, parsed: dict, price_range: dict) -> int | None:
    """Derive IPO size only from high-confidence cover-page offering terms.

    Do not use generic ``maximum aggregate offering price`` text from the filing.
    SEC registration-fee tables use that same label and can otherwise be mistaken
    for the actual deal size. A value is published only when the filing parser has
    a conflict-free, high-confidence base-offering share count from the prospectus
    cover/Offering section, multiplied by an explicit price range midpoint or fixed
    offering price. Greenshoe shares are excluded by the upstream terms parser.
    """
    cover = parsed.get("cover_page", {}) if isinstance(parsed, dict) else {}
    if cover.get("offering_size_conflict"):
        return None
    if str(cover.get("offering_size_confidence") or "").strip().lower() != "high":
        return None

    try:
        shares = int(cover.get("offering_size_shares") or 0)
    except (TypeError, ValueError):
        shares = 0
    if shares <= 0:
        return None

    try:
        low = float(price_range.get("range_low"))
        high = float(price_range.get("range_high"))
    except (TypeError, ValueError):
        low = high = 0
    if low > 0 and high > 0:
        return int(round(shares * ((low + high) / 2)))

    try:
        fixed_price = float(cover.get("offering_price") or 0)
    except (TypeError, ValueError):
        fixed_price = 0
    if fixed_price > 0:
        return int(round(shares * fixed_price))
    return None


def _size_provenance(cover: dict, ipo_size) -> tuple[str | None, str | None]:
    """Preserve authoritative offering-size evidence for downstream release gates.

    The parser already classifies the share-count evidence. Keep that provenance
    attached to the S-1 record instead of dropping it at the queue handoff. When
    the parser has an explicit primary-share count, add a canonical primary-offering
    marker so fixed-price IPOs with both issuer and selling-holder shares remain
    distinguishable from resale-only registrations without weakening the gate.
    """
    if not ipo_size:
        return None, None
    source = str(cover.get("offering_size_source") or "").strip()
    confidence = str(cover.get("offering_size_confidence") or "").strip()
    try:
        primary_shares = int(cover.get("primary_offering_shares") or 0)
    except (TypeError, ValueError):
        primary_shares = 0
    if primary_shares > 0 and source and "primary offering" not in source.casefold():
        source = f"primary offering; {source}"
    return source or None, confidence or None


def enrich_record(meta: dict, *, raise_errors: bool = False) -> dict | None:
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
        cover = parsed.get("cover_page", {}) if isinstance(parsed, dict) else {}

        # Narrow fallback for explicit fixed-price issuer IPO covers. Only fill
        # fields the generic parser did not already establish.
        fixed_terms = _explicit_fixed_price_primary_terms(filing_text)
        if fixed_terms:
            if not cover.get("offering_price"):
                cover["offering_price"] = fixed_terms["price"]
            if not cover.get("offering_size_shares"):
                cover["offering_size_shares"] = fixed_terms["shares"]
            if not cover.get("primary_offering_shares"):
                cover["primary_offering_shares"] = fixed_terms["shares"]
            if not cover.get("offering_size_source"):
                cover["offering_size_source"] = fixed_terms["source"]
            if not cover.get("offering_size_confidence"):
                cover["offering_size_confidence"] = fixed_terms["confidence"]
            if cover.get("offering_size_conflict") is None:
                cover["offering_size_conflict"] = False

        fixed_price_label = _format_fixed_price(cover.get("offering_price"))
        filing_price_label = range_label or fixed_price_label
        ipo_size = _extract_ipo_size(filing_text, parsed, price_range)
        if _is_micro_self_underwritten_offering(filing_text, parsed, ipo_size):
            return None
        offering_size_source, offering_size_confidence = _size_provenance(cover, ipo_size)

        ticker = str(cover.get("ticker") or "").strip().upper() or None
        if not ticker:
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
        elif fixed_price_label:
            signals.append(f"Fixed offering price disclosed at {fixed_price_label} per share")
        else:
            signals.append("No preliminary price range or fixed offering price detected yet")
        if ipo_size:
            signals.append(f"IPO size disclosed or derived at approximately ${ipo_size:,.0f}")

        return {
            "id": meta["accession_no"],
            "company": company,
            "ticker": ticker or "",
            "cik": str(cik).zfill(10) if cik else "",
            "accession_no": meta["accession_no"],
            "form": form,
            "filed": _normalize_filing_date(meta.get("filing_date") or ""),
            "stage": "Pre-pricing",
            "priority": "High" if (range_label or fixed_price_label) else "Medium",
            "price_range": range_label,
            "filing_price": filing_price_label,
            "ipo_size": ipo_size,
            "offering_size_source": offering_size_source,
            "offering_size_confidence": offering_size_confidence,
            "primary_offering_shares": cover.get("primary_offering_shares"),
            "secondary_offering_shares": cover.get("secondary_offering_shares"),
            "signals": signals,
            "sec_url": index_url,
        }
    except Exception as error:
        if raise_errors:
            raise
        print(f"[s1_monitor] Skipping {company}: {error}")
        return None


def evaluate_record(meta: dict) -> tuple[dict | None, bool]:
    """Return the candidate result plus whether SEC evaluation completed successfully.

    Deterministic exclusions are successful evaluations and may remove stale state.
    Transient/parser failures are not, so prior published state is preserved rather
    than being deleted merely because SEC enrichment failed during this run.
    """
    company = meta.get("company_name") or "Unknown"
    try:
        return enrich_record(meta, raise_errors=True), True
    except Exception as error:
        print(f"[s1_monitor] Evaluation failed for {company}: {error}")
        return None, False


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


def export_feed(
    records: list[dict],
    output_path: Path = OUTPUT_PATH,
    processed_ciks: set[str] | None = None,
) -> dict:
    """Merge current S-1 results and prune successfully reevaluated stale issuer state."""
    output_path = Path(output_path)
    existing = []
    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8")).get("filings", [])
        except (OSError, json.JSONDecodeError):
            existing = []

    processed_ciks = {
        str(cik or "").zfill(10) for cik in (processed_ciks or set()) if cik
    }
    merged = {
        item.get("id"): item
        for item in existing
        if isinstance(item, dict)
        and item.get("id")
        and str(item.get("cik") or "").zfill(10) not in processed_ciks
    }
    merged.update({item["id"]: item for item in records if item.get("id")})
    payload = build_payload(list(merged.values()))
    payload["filings"] = payload["filings"][:MAX_RECORDS]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp = output_path.with_suffix(output_path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temp.replace(output_path)
    return payload


def _queue_record(record: dict) -> dict:
    """Normalize a pre-pricing record to the V1 public dashboard schema."""
    cik = str(record.get("cik") or "").zfill(10) if record.get("cik") else ""
    ipo_size = record.get("ipo_size")
    return {
        "id": f"s1:{cik or record.get('company', '')}",
        "company": record.get("company") or "Unknown",
        "ticker": record.get("ticker") or "",
        "cik": cik,
        "accession_no": record.get("accession_no") or record.get("id") or "",
        "form": record.get("form") or "S-1",
        "filed": _normalize_filing_date(record.get("filed") or ""),
        "stage": record.get("stage") or "Pre-pricing",
        "price_range": record.get("price_range"),
        "filing_price": record.get("filing_price"),
        "offering_size_source": record.get("offering_size_source"),
        "offering_size_confidence": record.get("offering_size_confidence"),
        "primary_offering_shares": record.get("primary_offering_shares"),
        "secondary_offering_shares": record.get("secondary_offering_shares"),
        "priority": record.get("priority") or "Medium",
        "status": "New",
        "value": ipo_size,
        "value_label": "—" if not ipo_size else f"${ipo_size:,.0f}",
        "people_count": 0,
        "signals": list(record.get("signals") or []),
        "people": [],
        "sec_url": record.get("sec_url") or "https://www.sec.gov/edgar/search/",
    }


def sync_research_queue(
    records: list[dict], queue_path: Path = QUEUE_PATH, processed_ciks: set[str] | None = None
) -> dict:
    """Merge current S-1 signals into the queue and prune processed records that no longer qualify."""
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

    processed_ciks = {
        str(cik or "").zfill(10) for cik in (processed_ciks or set()) if cik
    }
    for item in existing:
        if isinstance(item, dict) and str(item.get("id", "")).startswith("s1:"):
            item["filed"] = _normalize_filing_date(item.get("filed") or "")

    merged = {
        item["id"]: item
        for item in existing
        if isinstance(item, dict)
        and item.get("id")
        and not (
            str(item.get("id", "")).startswith("s1:")
            and (
                str(item.get("cik") or "").zfill(10) in priced_ciks
                or str(item.get("cik") or "").zfill(10) in processed_ciks
            )
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
    temp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temp.replace(queue_path)
    write_dashboard_csv(payload["filings"], queue_path)
    return payload


def run(days_back: int = 4) -> dict:
    candidates = discover_recent_s1(days_back=days_back)
    print(f"[s1_monitor] Found {len(candidates)} recent S-1/S-1A filing(s).")
    records = []
    processed_ciks = set()
    for index, meta in enumerate(candidates, 1):
        print(
            f"[s1_monitor] Processing {index}/{len(candidates)}: "
            f"{meta['company_name']} ({meta['form_type']})"
        )
        record, evaluated = evaluate_record(meta)
        if evaluated and meta.get("cik"):
            processed_ciks.add(str(meta.get("cik") or "").zfill(10))
        if record:
            records.append(record)
    payload = export_feed(records, processed_ciks=processed_ciks)
    queue = sync_research_queue(records, processed_ciks=processed_ciks)
    print(f"[s1_monitor] Feed now contains {len(payload['filings'])} pre-pricing filing(s).")
    print(f"[s1_monitor] Research queue now contains {len(queue['filings'])} filing(s).")
    return payload


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SEC Research Monitor pre-pricing S-1 watcher")
    parser.add_argument("days_back", nargs="?", type=int, default=4)
    args = parser.parse_args()
    run(args.days_back)

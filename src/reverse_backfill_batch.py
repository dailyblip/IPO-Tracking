"""Append a small reverse-chronological batch of older qualifying IPOs.

This is a V1 stabilization tool, not a bulk historical loader. It starts immediately
before the oldest priced 424B4 currently in the public feed, scans backwards through
SEC EDGAR, and stops after exactly ``limit`` additional filings successfully produce
research rows through the normal production parser.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import dashboard_export
import edgar_client
import main
import qc_review
import sheets_writer

ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "docs" / "data" / "filings.json"
DEFAULT_LIMIT = 10
DEFAULT_SCAN_DAYS = 90


def oldest_priced_date(payload: dict) -> date:
    dates = []
    for filing in payload.get("filings", []):
        if str(filing.get("form") or "").upper() != "424B4":
            continue
        if str(filing.get("stage") or "").lower() != "priced":
            continue
        raw = filing.get("pricing_date") or filing.get("filed")
        try:
            dates.append(datetime.fromisoformat(str(raw)[:10]).date())
        except (TypeError, ValueError):
            continue
    if not dates:
        raise RuntimeError("Public feed has no dated priced 424B4 record to extend backwards from.")
    return min(dates)


def _candidate_key(filing: dict) -> str:
    return str(filing.get("accession_no") or "").strip()


def select_candidates(filings: list[dict], cutoff: date, existing_ids: set[str]) -> list[dict]:
    eligible = []
    for filing in filings:
        accession = _candidate_key(filing)
        try:
            filed = datetime.fromisoformat(str(filing.get("filing_date") or "")[:10]).date()
        except ValueError:
            continue
        if not accession or accession in existing_ids or filed >= cutoff:
            continue
        eligible.append(filing)
    eligible.sort(
        key=lambda item: (str(item.get("filing_date") or ""), _candidate_key(item)),
        reverse=True,
    )
    return eligible


def run(limit: int = DEFAULT_LIMIT, scan_days: int = DEFAULT_SCAN_DAYS) -> list[str]:
    if limit < 1:
        raise ValueError("limit must be positive")
    if scan_days < 1:
        raise ValueError("scan_days must be positive")

    payload = json.loads(FEED_PATH.read_text(encoding="utf-8"))
    cutoff = oldest_priced_date(payload)
    existing_ids = {
        str(filing.get("accession_no") or filing.get("id") or "").strip()
        for filing in payload.get("filings", [])
    }
    search_end = cutoff - timedelta(days=1)
    search_start = search_end - timedelta(days=scan_days - 1)

    print(
        f"[reverse-backfill] Current oldest priced IPO date: {cutoff.isoformat()}; "
        f"scanning {search_start.isoformat()} through {search_end.isoformat()} for {limit} additions."
    )
    discovered = edgar_client.find_recent_424b4_filings(
        start_date=search_start.isoformat(),
        end_date=search_end.isoformat(),
    )
    candidates = select_candidates(discovered, cutoff, existing_ids)
    print(f"[reverse-backfill] {len(candidates)} older 424B4 candidate(s) discovered.")

    all_rows = []
    accepted_accessions = []
    for filing_meta in candidates:
        if len(accepted_accessions) >= limit:
            break
        print(
            f"[reverse-backfill] Evaluating {filing_meta.get('company_name')} "
            f"({filing_meta.get('filing_date')})."
        )
        rows = main.process_filing(filing_meta)
        if not rows:
            continue
        index_url = edgar_client.build_filing_index_url(
            filing_meta["cik"], filing_meta["accession_no"]
        )
        for row in rows:
            row.update({
                "_cik": filing_meta.get("cik", ""),
                "_accession_no": filing_meta.get("accession_no", ""),
                "_form": filing_meta.get("form_type") or "424B4",
                "_sec_url": index_url,
            })
        all_rows.extend(rows)
        accepted_accessions.append(filing_meta["accession_no"])

    if len(accepted_accessions) != limit:
        raise RuntimeError(
            f"Only {len(accepted_accessions)} qualifying IPO(s) were found in the "
            f"{scan_days}-day scan; refusing a partial batch of {limit}."
        )

    spreadsheet_id = os.environ.get("SPREADSHEET_ID")
    previous_rows_by_key = {}
    if spreadsheet_id:
        try:
            previous_rows_by_key = sheets_writer.fetch_existing_rows(spreadsheet_id)
        except Exception as error:
            print(f"[reverse-backfill] Sheet comparison unavailable: {error}")

    source_excerpts_by_key = {}
    for row in all_rows:
        key = (str(row.get("Ticker") or "").upper(), str(row.get("Holder Name") or "").strip().lower())
        source_excerpts_by_key[key] = row.pop("_source_excerpt", "")

    reviewed_rows = qc_review.review_rows(
        all_rows,
        previous_rows_by_key=previous_rows_by_key,
        source_excerpts_by_key=source_excerpts_by_key,
    )
    dashboard = dashboard_export.export_dashboard(reviewed_rows, FEED_PATH)
    main._refresh_dashboard_prices(dashboard)

    if spreadsheet_id:
        try:
            sheets_writer.upsert_rows(spreadsheet_id, reviewed_rows)
        except Exception as error:
            print(f"[reverse-backfill] Sheet write deferred: {error}")

    print("[reverse-backfill] Added accessions:")
    for accession in accepted_accessions:
        print(f"  - {accession}")
    return accepted_accessions


def main_cli() -> None:
    parser = argparse.ArgumentParser(description="Add a controlled reverse batch of older IPOs")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--scan-days", type=int, default=DEFAULT_SCAN_DAYS)
    args = parser.parse_args()
    run(limit=args.limit, scan_days=args.scan_days)


if __name__ == "__main__":
    main_cli()

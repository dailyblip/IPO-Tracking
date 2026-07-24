"""
main.py

Orchestrates the full daily pipeline:
1. Discover recent 424B4 filings (US-based, non-SPAC only)
2. Parse each filing: cover page, ownership grid, bios, lock-up info
3. Pull the matching S-1 for the original filing-range price
4. Look up current market prices and compute cash values per holder
5. Grade each holder's Stanford affiliation
6. Run QC checks against the assembled rows
7. Upsert everything to the shared Google Sheet

Run daily via GitHub Actions (.github/workflows/daily.yml). Can also be
run manually: python main.py [days_back]
"""

import os
import sys
from datetime import date

import edgar_client
import filing_parser
import price_lookup
import stanford_grader
import qc_review
import sheets_writer

DEFAULT_LOOKBACK_DAYS = 2  # covers EDGAR indexing lag; upsert dedupes overlap


def _get_spreadsheet_id() -> str:
    spreadsheet_id = os.environ.get("SPREADSHEET_ID")
    if not spreadsheet_id:
        raise RuntimeError("SPREADSHEET_ID environment variable is not set.")
    return spreadsheet_id


def process_filing(filing_meta: dict) -> list:
    """
    Process a single 424B4 filing end to end. Returns a list of row
    dicts (one per beneficial owner), or an empty list if the filing
    should be skipped (non-US, likely SPAC, or a parsing failure).
    Never raises - logs and returns [] on failure so one bad filing
    doesn't take down the whole run.
    """
    company_name = filing_meta["company_name"]
    cik = filing_meta["cik"]

    try:
        if not edgar_client.is_us_based(cik):
            print(f"[main] Skipping {company_name} (CIK {cik}): not US-based")
            return []

        index_url = edgar_client.build_filing_index_url(cik, filing_meta["accession_no"])
        document_url = filing_parser.find_primary_document_url(index_url, expected_form_types=["424B4"])

        parsed = filing_parser.parse_filing(document_url)

        full_text_soup = filing_parser.fetch_document(document_url)
        if edgar_client.check_spac_indicators(full_text_soup.get_text(" ", strip=True)):
            print(f"[main] Flagging {company_name} (CIK {cik}): possible SPAC language detected - skipping")
            return []

        cover = parsed["cover_page"]
        ticker = cover.get("ticker")
        actual_price = cover.get("offering_price")

        stockholder_count = len(parsed.get("principal_stockholders", []))
        bio_count = len([k for k in parsed.get("management_bios", {}) if k != "_full_text"])
        print(
            f"[main] {company_name}: ticker={ticker}, offering_price={actual_price}, "
            f"stockholders_found={stockholder_count}, bios_split={bio_count}, "
            f"lockup_text_found={bool(parsed.get('lockup_info', {}).get('raw_text'))}"
        )

        if not ticker:
            print(f"[main] Skipping {company_name}: could not extract ticker")
            return []

        # Pull the matching S-1 for the original range price.
        s1_meta = edgar_client.find_matching_s1(cik)
        filing_price = None
        if s1_meta:
            try:
                s1_index_url = edgar_client.build_filing_index_url(cik, s1_meta["accession_no"])
                s1_document_url = filing_parser.find_primary_document_url(
                    s1_index_url, expected_form_types=["S-1", "S-1/A"]
                )
                s1_parsed = filing_parser.parse_filing(s1_document_url, is_range_filing=True)
                price_range = s1_parsed.get("price_range", {})
                if price_range.get("range_low") and price_range.get("range_high"):
                    filing_price = f"{price_range['range_low']}-{price_range['range_high']}"
            except Exception as e:
                print(f"[main] Warning: could not parse S-1 for {company_name}: {e}")

        current_price = None
        if ticker:
            try:
                current_price = price_lookup.get_current_price(ticker)
            except price_lookup.PriceLookupError as e:
                print(f"[main] Warning: could not get current price for {ticker}: {e}")
                # Continue anyway - qc_review.py will flag the missing
                # price rather than losing this filing's rows entirely.
        lockup = parsed.get("lockup_info", {})
        bios = parsed.get("management_bios", {})

        rows = []
        for holder in parsed.get("principal_stockholders", []):
            holder_name = holder["name"]
            shares = holder.get("shares")

            # Try to find this holder's bio text by substring match on
            # the bio dict keys (falls back to the full management text).
            bio_text = bios.get(holder_name, "") or bios.get("_full_text", "")

            stanford_result = stanford_grader.grade_stanford_affiliation(
                person_name=holder_name,
                company_name=company_name,
                bio_text=bio_text,
            )

            cash_value = (shares * current_price) if (shares and current_price) else None

            rows.append({
                "Company Name": company_name,
                "Ticker": ticker,
                "Filing Price": filing_price,
                "Actual Price": actual_price,
                "Current Price": current_price,
                "Holder Name": holder_name,
                "Shares": shares,
                "Cash Value": cash_value,
                "Stanford Grade": stanford_result["grade"],
                "Stanford Justification": stanford_result["justification"],
                "Lock-Up Expiry": lockup.get("raw_text", "")[:200] if lockup.get("raw_text") else "",
                "Last Updated": date.today().isoformat(),
                "_source_excerpt": bio_text[:500],  # consumed by qc_review, stripped before writing
            })

        return rows

    except Exception as e:
        print(f"[main] ERROR processing {company_name} (CIK {cik}): {e}")
        return []


def run(days_back: int = DEFAULT_LOOKBACK_DAYS):
    spreadsheet_id = _get_spreadsheet_id()

    print(f"[main] Discovering 424B4 filings from the last {days_back} day(s)...")
    filings = edgar_client.find_recent_424b4_filings(days_back=days_back)
    print(f"[main] Found {len(filings)} filing(s) to evaluate.")

    all_rows = []
    for filing_meta in filings:
        rows = process_filing(filing_meta)
        all_rows.extend(rows)

    if not all_rows:
        print("[main] No rows produced this run. Nothing to write.")
        return

    print(f"[main] Fetching previous run's data for QC comparison...")
    previous_rows_by_key = sheets_writer.fetch_existing_rows(spreadsheet_id)

    source_excerpts_by_key = {}
    for row in all_rows:
        key = (row["Ticker"].upper(), row["Holder Name"].strip().lower())
        source_excerpts_by_key[key] = row.pop("_source_excerpt", "")

    print(f"[main] Running QC checks on {len(all_rows)} row(s)...")
    reviewed_rows = qc_review.review_rows(
        all_rows,
        previous_rows_by_key=previous_rows_by_key,
        source_excerpts_by_key=source_excerpts_by_key,
    )

    print(f"[main] Writing to Google Sheet...")
    summary = sheets_writer.upsert_rows(spreadsheet_id, reviewed_rows)

    print(
        f"[main] Done. New: {summary['new']}, Updated: {summary['updated']}, "
        f"Flagged for review: {summary['flagged']}"
    )


if __name__ == "__main__":
    days_arg = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LOOKBACK_DAYS
    run(days_back=days_arg)

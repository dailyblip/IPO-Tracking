"""
main.py

Orchestrates the full daily pipeline:
1. Discover recent 424B4 filings (US-based, non-SPAC only)
2. Parse each filing: cover page, ownership grid, bios, lock-up info
3. Pull the matching S-1 for the original filing-range price
4. Look up current market prices and compute cash values per holder
5. Grade beneficial owners plus named executives/directors for Stanford affiliation
6. Run QC checks against the assembled rows
7. Upsert everything to the shared Google Sheet

Run daily via GitHub Actions (.github/workflows/daily.yml). Can also be
run manually: python main.py [days_back]
"""

import os
import json
import re
import sys
from datetime import date
from pathlib import Path

import edgar_client
import filing_parser
import price_lookup
import stanford_grader
import qc_review
import sheets_writer
import dashboard_export

DASHBOARD_OUTPUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"


def _default_lookback_days(today=None):
    """Cover the previous two business days, including intervening weekends."""
    today = today or date.today()
    cursor = today
    business_days = 0
    while business_days < 2:
        cursor = date.fromordinal(cursor.toordinal() - 1)
        if cursor.weekday() < 5:
            business_days += 1
    return (today - cursor).days


DEFAULT_LOOKBACK_DAYS = _default_lookback_days()


def _person_key(person_name):
    """Stable comparison key for person names extracted from different SEC sections."""
    return " ".join(re.findall(r"[a-z0-9]+", str(person_name or "").casefold()))


def _person_bio(bios, person_name):
    """Return only the bio belonging to this named person, never the full-text fallback."""
    target = _person_key(person_name)
    if not target:
        return ""
    for name, bio in (bios or {}).items():
        if name == "_full_text":
            continue
        candidate = _person_key(name)
        if candidate and (
            candidate == target
            or candidate.startswith(f"{target} ")
            or target.startswith(f"{candidate} ")
        ):
            return str(bio or "")
    return ""


def _management_bio_candidates(bios, holder_names):
    """Return named management/director bios not already represented by an owner row."""
    holder_keys = {_person_key(name) for name in holder_names if _person_key(name)}
    candidates = []
    for name, bio in (bios or {}).items():
        if name == "_full_text" or not str(name or "").strip():
            continue
        key = _person_key(name)
        if not key or key in holder_keys:
            continue
        candidates.append((str(name).strip(), str(bio or "")))
    return candidates


def _mentions_stanford_university(bio_text):
    return bool(re.search(r"\bstanford\s+university\b", str(bio_text or ""), re.I))


def _role_from_bio(bio_text):
    """Extract a conservative current title from the holder's filing bio."""
    text = " ".join(str(bio_text or "").split())
    patterns = [
        r"(?:has served|serves) as (?:our|the) ([^.]{2,100}?)(?: since| and|\.|,)",
        r"(?:is|is currently) (?:our|the) ([^.]{2,100}?)(?:\.|,| and)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            role = match.group(1).strip(" ,.;")
            if role and len(role) <= 100:
                return role
    return None


def _refresh_dashboard_prices(dashboard):
    """Refresh delayed quotes for every trading ticker already in the public queue."""
    tickers = sorted({
        str(filing.get("ticker") or "").strip().upper()
        for filing in (dashboard or {}).get("filings", [])
        if str(filing.get("ticker") or "").strip()
    })
    if not tickers:
        return dashboard
    prices = price_lookup.get_current_prices(tickers)
    return dashboard_export.refresh_market_prices(
        DASHBOARD_OUTPUT_PATH,
        prices,
    ) or dashboard


def _get_spreadsheet_id() -> str:
    spreadsheet_id = os.environ.get("SPREADSHEET_ID")
    if not spreadsheet_id:
        raise RuntimeError("SPREADSHEET_ID environment variable is not set.")
    return spreadsheet_id


def process_filing(filing_meta: dict) -> list:
    """
    Process a single 424B4 filing end to end. Returns a list of row
    dicts (one per beneficial owner, plus confirmed Stanford-affiliated
    management/director people), or an empty list if the filing should be
    skipped (non-US, likely SPAC, or a parsing failure).
    Never raises - logs and returns [] on failure so one bad filing
    doesn't take down the whole run.
    """
    company_name = filing_meta["company_name"]
    cik = filing_meta["cik"]

    try:
        if not edgar_client.is_us_based(cik):
            print(f"[main] Skipping {company_name}: not US-based")
            return []

        if not edgar_client.is_first_time_registrant(cik):
            print(
                f"[main] Skipping {company_name}: already an SEC "
                f"reporting company (has a prior 10-K) - this 424B4 is a "
                f"follow-on/resale offering, not a first-time IPO"
            )
            return []

        s1_meta = edgar_client.find_matching_s1(cik)
        if not s1_meta:
            print(
                f"[main] Skipping {company_name}: no S-1/S-1A registration found; "
                f"likely a foreign private issuer or non-domestic offering"
            )
            return []

        index_url = edgar_client.build_filing_index_url(cik, filing_meta["accession_no"])
        document_url = filing_parser.find_primary_document_url(index_url, expected_form_types=["424B4"])

        parsed = filing_parser.parse_filing(document_url)

        full_text_soup = filing_parser.fetch_document(document_url)
        filing_text = full_text_soup.get_text(" ", strip=True)
        if edgar_client.check_spac_indicators(
            filing_text, company_name=company_name
        ):
            print(f"[main] Flagging {company_name}: possible SPAC language detected - skipping")
            return []
        if edgar_client.check_direct_listing_indicators(filing_text):
            print(
                f"[main] Skipping {company_name}: direct listing/resale prospectus, "
                f"not an underwritten primary IPO"
            )
            return []

        cover = parsed["cover_page"]
        ticker = cover.get("ticker") or filing_meta.get("ticker")
        if not ticker:
            try:
                ticker = edgar_client.get_primary_ticker(cik)
            except Exception as error:
                print(f"[main] Warning: could not resolve SEC ticker for {company_name}: {error}")
        actual_price = cover.get("offering_price")

        stockholder_count = len(parsed.get("principal_stockholders", []))
        bio_count = len([k for k in parsed.get("management_bios", {}) if k != "_full_text"])
        diagnostics = parsed.get("diagnostics", {})
        print(
            f"[main] {company_name}: ticker={ticker}, offering_price={actual_price}, "
            f"stockholders_found={stockholder_count}, bios_split={bio_count}, "
            f"lockup_text_found={bool(parsed.get('lockup_info', {}).get('raw_text'))}, "
            f"page_text_length={diagnostics.get('page_text_length')}, "
            f"ownership_keyword_present={diagnostics.get('ownership_keyword_present')}, "
            f"management_keyword_present={diagnostics.get('management_keyword_present')}, "
            f"underwriting_keyword_present={diagnostics.get('underwriting_keyword_present')}"
        )

        filing_price = None
        s1_location = None
        date_of_filing = s1_meta.get("filing_date") if s1_meta else None
        if s1_meta:
            try:
                s1_index_url = edgar_client.build_filing_index_url(cik, s1_meta["accession_no"])
                s1_document_url = filing_parser.find_primary_document_url(
                    s1_index_url, expected_form_types=["S-1", "S-1/A"]
                )
                s1_parsed = filing_parser.parse_filing(s1_document_url, is_range_filing=True)
                s1_location = s1_parsed.get("principal_office_location")
                price_range = s1_parsed.get("price_range", {})
                if price_range.get("range_low") and price_range.get("range_high"):
                    filing_price = f"{price_range['range_low']}-{price_range['range_high']}"
            except Exception as e:
                print(f"[main] Warning: could not parse S-1 for {company_name}: {e}")

        date_of_pricing = filing_meta.get("filing_date")

        offering_size = cover.get("offering_size_shares")
        primary_offering_shares = cover.get("primary_offering_shares")
        secondary_offering_shares = cover.get("secondary_offering_shares")
        offering_size_source = cover.get("offering_size_source")
        offering_size_confidence = cover.get("offering_size_confidence")
        offering_size_conflict = bool(cover.get("offering_size_conflict"))
        amount_raised = (
            offering_size * actual_price if (offering_size and actual_price) else None
        )

        current_price = None
        if ticker:
            try:
                current_price = price_lookup.get_current_price(ticker)
            except price_lookup.PriceLookupError as e:
                print(f"[main] Warning: could not get current price for {ticker}: {e}")
        lockup = parsed.get("lockup_info", {})
        bios = parsed.get("management_bios", {})
        business_location = parsed.get("principal_office_location") or s1_location
        location_source = (
            "424B4 principal executive office" if parsed.get("principal_office_location")
            else ("S-1 principal executive office" if s1_location else None)
        )
        if not business_location:
            try:
                business_location = edgar_client.get_business_location(cik)
                location_source = "SEC submissions metadata" if business_location else None
            except Exception as error:
                print(f"[main] Warning: could not resolve issuer location for {company_name}: {error}")
                business_location = ""
                location_source = None

        rows = []
        holders = parsed.get("principal_stockholders", [])
        original_holder_names = [holder.get("name", "") for holder in holders]
        if not holders:
            holders = [{"name": "", "shares": None}]

        for holder in holders:
            holder_name = holder["name"]
            shares_before = holder.get("shares_before")
            shares_sold = holder.get("shares_sold")
            shares_after = holder.get("shares_after")
            if shares_after is None and shares_before is not None and shares_sold is not None:
                derived_after = shares_before - shares_sold
                if derived_after >= 0:
                    shares_after = derived_after
            shares = shares_after if shares_after is not None else holder.get("shares")
            percent_before = holder.get("percent_before")
            percent_after = holder.get("percent_after") if holder.get("percent_after") is not None else holder.get("percent")

            person_bio_text = _person_bio(bios, holder_name)
            bio_text = person_bio_text or bios.get("_full_text", "")
            stanford_university_in_bio = _mentions_stanford_university(person_bio_text)

            if holder_name:
                try:
                    stanford_result = stanford_grader.grade_stanford_affiliation(
                        person_name=holder_name,
                        company_name=company_name,
                        bio_text=bio_text,
                    )
                except Exception as e:
                    print(f"[main] Warning: Stanford grading failed for {holder_name} "
                          f"({company_name}): {e}")
                    stanford_result = {
                        "grade": 0,
                        "justification": f"Grading failed to run: {e}",
                    }
            else:
                stanford_result = {
                    "grade": 0,
                    "justification": "No named beneficial owner was parsed.",
                }

            cash_value = (shares * current_price) if (shares and current_price) else None

            rows.append({
                "Company Name": company_name,
                "Ticker": ticker,
                "Date of Filing": date_of_filing,
                "Date of Pricing": date_of_pricing,
                "Filing Price": filing_price,
                "Actual Price": actual_price,
                "IPO Size (Shares)": offering_size,
                "Primary Offering Shares": primary_offering_shares,
                "Secondary Offering Shares": secondary_offering_shares,
                "Offering Size Source": offering_size_source,
                "Offering Size Confidence": offering_size_confidence,
                "Offering Size Conflict": offering_size_conflict,
                "Amount Raised": amount_raised,
                "Current Price": current_price,
                "Location": business_location,
                "Location Source": location_source,
                "Holder Name": holder_name,
                "Role": _role_from_bio(person_bio_text),
                "Shares": shares,
                "Shares Before IPO": shares_before,
                "Shares Sold in IPO": shares_sold,
                "Shares After IPO": shares_after if shares_after is not None else shares,
                "Ownership % Before IPO": percent_before,
                "Ownership % After IPO": percent_after,
                "Cash Realized IPO": (shares_sold * actual_price) if (shares_sold is not None and actual_price) else None,
                "Cash Value": cash_value,
                "Stanford Grade": stanford_result["grade"],
                "Stanford Justification": stanford_result["justification"],
                "Stanford University in Bio": stanford_university_in_bio,
                "Stanford Affiliation Confirmed": bool(stanford_university_in_bio or stanford_result.get("grade") in (5, "5")),
                "Lock-Up Expiry": "",
                "Lock-Up Text": lockup.get("raw_text") or "",
                "Lock-Up Duration Days": lockup.get("duration_days"),
                "Lock-Up Duration Value": lockup.get("duration_value"),
                "Lock-Up Duration Unit": lockup.get("duration_unit"),
                "Lock-Up Scope": lockup.get("scope") or "",
                "Lock-Up Scope Tags": ",".join(lockup.get("scope_tags") or []),
                "Lock-Up Terms JSON": json.dumps(lockup.get("terms") or [], ensure_ascii=False),
                "Lock-Up Confidence": lockup.get("confidence") or "Unresolved",
                "Lock-Up Structured": bool(lockup.get("structured")),
                "Lock-Up Language Present": bool(
                    lockup.get("raw_text")
                    or parsed.get("diagnostics", {}).get("underwriting_keyword_present")
                ),
                "Last Updated": date.today().isoformat(),
                "_source_excerpt": bio_text[:500],
            })

        # Stanford is a company-level research signal, not only an ownership-table
        # signal. Grade each named management/director bio that was not already
        # processed as a beneficial owner. To avoid polluting the ownership view,
        # only confirmed Stanford-affiliated management people are added.
        for person_name, person_bio_text in _management_bio_candidates(
            bios, original_holder_names
        ):
            try:
                stanford_result = stanford_grader.grade_stanford_affiliation(
                    person_name=person_name,
                    company_name=company_name,
                    title=_role_from_bio(person_bio_text) or "",
                    bio_text=person_bio_text,
                )
            except Exception as e:
                print(
                    f"[main] Warning: Stanford grading failed for management person "
                    f"{person_name} ({company_name}): {e}"
                )
                continue

            direct_stanford = _mentions_stanford_university(person_bio_text)
            confirmed = bool(
                direct_stanford or stanford_result.get("grade") in (5, "5")
            )
            if not confirmed:
                continue

            template = dict(rows[0])
            template.update({
                "Holder Name": person_name,
                "Role": _role_from_bio(person_bio_text),
                "Shares": None,
                "Shares Before IPO": None,
                "Shares Sold in IPO": None,
                "Shares After IPO": None,
                "Ownership % Before IPO": None,
                "Ownership % After IPO": None,
                "Cash Realized IPO": None,
                "Cash Value": None,
                "Stanford Grade": stanford_result.get("grade", 5),
                "Stanford Justification": stanford_result.get("justification", "Confirmed Stanford affiliation."),
                "Stanford University in Bio": direct_stanford,
                "Stanford Affiliation Confirmed": True,
                "_source_excerpt": person_bio_text[:500],
            })
            rows.append(template)
            print(
                f"[main] Stanford connection confirmed for management/director "
                f"{person_name} ({company_name})"
            )

        return rows

    except Exception as e:
        print(f"[main] ERROR processing {company_name}: {e}")
        return []


def run(days_back: int = DEFAULT_LOOKBACK_DAYS, start_date: str = None, end_date: str = None):
    spreadsheet_id = _get_spreadsheet_id()

    if start_date:
        print(f"[main] Discovering 424B4 filings from {start_date} to {end_date or 'today'}...")
        filings = edgar_client.find_recent_424b4_filings(start_date=start_date, end_date=end_date)
    else:
        print(f"[main] Discovering 424B4 filings from the last {days_back} day(s)...")
        filings = edgar_client.find_recent_424b4_filings(days_back=days_back)
    print(f"[main] Found {len(filings)} filing(s) to evaluate.")

    all_rows = []
    for i, filing_meta in enumerate(filings, 1):
        print(f"[main] Processing {i}/{len(filings)}: {filing_meta.get('company_name')} "
              f"(filed {filing_meta.get('filing_date')})")
        rows = process_filing(filing_meta)
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

    if not all_rows:
        print("[main] No rows produced this run. Refreshing dashboard metadata...")
        dashboard = dashboard_export.export_dashboard(
            [],
            DASHBOARD_OUTPUT_PATH,
            replace_start=start_date,
            replace_end=(end_date or date.today().isoformat()) if start_date else None,
        )
        _refresh_dashboard_prices(dashboard)
        try:
            sheets_writer.ensure_tabs_exist(spreadsheet_id)
        except Exception as error:
            print(
                f"[main] WARNING: Google Sheet unavailable; dashboard refresh "
                f"will continue and Sheets will retry next run: {error}"
            )
        print("[main] Dashboard feed checked; no data to write this run.")
        return

    print(f"[main] Fetching previous run's data for QC comparison...")
    try:
        previous_rows_by_key = sheets_writer.fetch_existing_rows(spreadsheet_id)
    except Exception as error:
        print(
            f"[main] WARNING: Could not read previous Sheet rows; "
            f"continuing without cross-run comparison: {error}"
        )
        previous_rows_by_key = {}

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

    dashboard = dashboard_export.export_dashboard(
        reviewed_rows,
        DASHBOARD_OUTPUT_PATH,
        replace_start=start_date,
        replace_end=(end_date or date.today().isoformat()) if start_date else None,
    )
    dashboard = _refresh_dashboard_prices(dashboard)
    print(
        f"[main] Exported dashboard feed with {len(dashboard['filings'])} filing(s) "
        f"to {DASHBOARD_OUTPUT_PATH}"
    )

    print(f"[main] Writing to Google Sheet...")
    try:
        summary = sheets_writer.upsert_rows(spreadsheet_id, reviewed_rows)
    except Exception as error:
        print(
            f"[main] WARNING: Google Sheet write deferred until the next run: {error}"
        )
        summary = None

    if summary:
        print(
            f"[main] Done. New: {summary['new']}, Updated: {summary['updated']}, "
            f"Flagged for review: {summary['flagged']}"
        )
    else:
        print("[main] Done. Dashboard updated; Google Sheet sync deferred.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SEC IPO tracker daily pipeline")
    parser.add_argument("days_back", nargs="?", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument(
        "--test-cik", type=str, default=None,
        help="Bypass discovery and process this one specific CIK directly (for safe manual testing)"
    )
    parser.add_argument(
        "--test-accession", type=str, default=None,
        help="Accession number (with dashes) of the specific 424B4 to test, used with --test-cik"
    )
    parser.add_argument(
        "--test-company-name", type=str, default="Test Company",
        help="Display name to use for the test filing (optional, cosmetic only)"
    )
    parser.add_argument(
        "--test-spreadsheet-id", type=str, default=None,
        help="Write test results to this spreadsheet instead of SPREADSHEET_ID, "
             "so a manual test never touches production data"
    )
    parser.add_argument(
        "--backfill-start", type=str, default=None,
        help="Backfill mode: process all 424B4 filings from this date forward "
             "(YYYY-MM-DD) instead of the normal daily lookback window"
    )
    parser.add_argument(
        "--backfill-end", type=str, default=None,
        help="End date for backfill mode (YYYY-MM-DD). Defaults to today if omitted."
    )
    args = parser.parse_args()

    if args.test_cik and args.test_accession:
        spreadsheet_id = args.test_spreadsheet_id or os.environ.get("TEST_SPREADSHEET_ID")
        if not spreadsheet_id:
            print(
                "[main] ERROR: --test-cik requires either --test-spreadsheet-id or "
                "a TEST_SPREADSHEET_ID env var, so this never accidentally writes to production."
            )
            sys.exit(1)

        print(f"[main] TEST MODE: processing CIK {args.test_cik}, accession {args.test_accession}")
        print(f"[main] TEST MODE: writing to spreadsheet {spreadsheet_id} (not production)")

        rows = process_filing({
            "company_name": args.test_company_name,
            "cik": args.test_cik,
            "accession_no": args.test_accession,
        })

        if not rows:
            print("[main] TEST MODE: process_filing produced 0 rows. Check the log above for why.")
            sheets_writer.ensure_tabs_exist(spreadsheet_id)
        else:
            reviewed = qc_review.review_rows(rows)
            summary = sheets_writer.upsert_rows(spreadsheet_id, reviewed)
            print(f"[main] TEST MODE done. New: {summary['new']}, Updated: {summary['updated']}, "
                  f"Flagged: {summary['flagged']}")
    elif args.backfill_start:
        run(start_date=args.backfill_start, end_date=args.backfill_end)
    else:
        run(days_back=args.days_back)

"""
edgar_client.py

Discovers newly filed 424B4 (final IPO prospectus) filings on SEC EDGAR,
filters out non-US filers and SPACs, and locates the matching S-1/S-1A
for the same company so the original filing-range price can be captured
alongside the final offering price.

Requires SEC_EDGAR_USER_AGENT to be set as an environment variable -
SEC requires a descriptive User-Agent with a real contact email on
every request (e.g. "YourName your@email.com"), and will rate-limit or
block requests that don't provide one.
"""

import os
import time
import requests

EDGAR_FULL_TEXT_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

REQUEST_DELAY_SECONDS = 0.15  # keeps us under SEC's ~10 req/sec limit

# Heuristic phrases that show up on SPAC cover pages / Item 1 text.
# Anything matching gets flagged for manual review rather than silently
# dropped, since this is a heuristic, not a guarantee.
SPAC_INDICATOR_PHRASES = [
    "blank check company",
    "special purpose acquisition",
    "business combination with one or more businesses",
]


class EdgarClientError(Exception):
    pass


def _get_headers() -> dict:
    user_agent = os.environ.get("SEC_EDGAR_USER_AGENT")
    if not user_agent:
        raise EdgarClientError(
            "SEC_EDGAR_USER_AGENT environment variable is not set. "
            "SEC requires a descriptive User-Agent with a contact email, "
            "e.g. 'YourName your@email.com'."
        )
    return {"User-Agent": user_agent}


def find_recent_424b4_filings(days_back: int = 1, start_date: str = None,
                                end_date: str = None, max_results: int = 500) -> list:
    """
    Search EDGAR full-text search for 424B4 filings.

    Either pass days_back (default daily-run behavior: filings from the
    last N days), or pass start_date/end_date explicitly (YYYY-MM-DD,
    used for backfilling a historical range) - if both are given,
    start_date/end_date take precedence.

    Paginates automatically (EDGAR returns ~10 hits per page) up to
    max_results, since a multi-week or multi-month backfill window can
    easily exceed a single page across the whole market.
    """
    headers = _get_headers()
    effective_start = start_date or _date_days_ago(days_back)
    effective_end = end_date or _today()

    results = []
    offset = 0
    page_size = 10  # EDGAR full-text search's default page size

    while offset < max_results:
        params = {
            "forms": "424B4",
            "dateRange": "custom",
            "startdt": effective_start,
            "enddt": effective_end,
            "from": offset,
        }
        response = requests.get(
            EDGAR_FULL_TEXT_SEARCH_URL, headers=headers, params=params, timeout=15
        )
        response.raise_for_status()
        time.sleep(REQUEST_DELAY_SECONDS)
        data = response.json()

        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break

        for hit in hits:
            source = hit.get("_source", {})
            cik = source.get("ciks", [None])[0]
            accession_no = hit.get("_id", "").split(":")[0]
            results.append({
                "company_name": source.get("display_names", ["Unknown"])[0],
                "cik": cik,
                "accession_no": accession_no,
                "filing_date": source.get("file_date"),
                "form_type": source.get("root_form"),
            })

        total_available = data.get("hits", {}).get("total", {}).get("value", 0)
        offset += page_size
        if offset >= total_available:
            break

    return results


def is_us_based(cik: str) -> bool:
    """
    Check the filer's business address state/country via the EDGAR
    submissions API. Returns True if the filer's address country is US
    (or blank, which EDGAR uses for US addresses in some older filings).
    """
    headers = _get_headers()
    padded_cik = str(cik).zfill(10)
    url = EDGAR_SUBMISSIONS_URL.format(cik=padded_cik)

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    time.sleep(REQUEST_DELAY_SECONDS)

    address = data.get("addresses", {}).get("business", {})
    country = (address.get("countryOfIncorporation") or address.get("country") or "").strip()
    return country in ("", "US")


def check_spac_indicators(filing_text: str) -> bool:
    """
    Heuristic check for SPAC language in the filing's cover page / Item 1
    text. Returns True if any indicator phrase is found. This is a
    heuristic, not a guarantee - treat a True result as "flag for manual
    review," not an automatic exclusion, since legitimate operating
    companies occasionally reference "business combination" in unrelated
    contexts (e.g. describing a past acquisition).
    """
    lowered = filing_text.lower()
    return any(phrase in lowered for phrase in SPAC_INDICATOR_PHRASES)


def is_first_time_registrant(cik: str) -> bool:
    """
    Distinguishes a genuine first-time IPO from a follow-on or resale
    offering by an already-public company - both get filed on Form
    424B4, but only the former is actually an "IPO" in the sense this
    tracker cares about. Heuristic: a company that has already filed a
    10-K (annual report) is already an SEC reporting company, since
    10-Ks require a completed fiscal year of public reporting first -
    a fresh IPO company won't have one yet.
    """
    headers = _get_headers()
    padded_cik = str(cik).zfill(10)
    url = EDGAR_SUBMISSIONS_URL.format(cik=padded_cik)

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    data = response.json()

    forms = data.get("filings", {}).get("recent", {}).get("form", [])
    return not any(form == "10-K" for form in forms)


def find_matching_s1(cik: str) -> dict:
    """
    Find the most recent S-1 or S-1/A filed by the same CIK prior to the
    424B4, to capture the original filing-range price. Returns filing
    metadata, or an empty dict if none is found.
    """
    headers = _get_headers()
    padded_cik = str(cik).zfill(10)
    url = EDGAR_SUBMISSIONS_URL.format(cik=padded_cik)

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    time.sleep(REQUEST_DELAY_SECONDS)

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accession_numbers = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])

    for form, accession_no, filing_date in zip(forms, accession_numbers, filing_dates):
        if form in ("S-1", "S-1/A"):
            return {
                "form_type": form,
                "accession_no": accession_no,
                "filing_date": filing_date,
            }

    return {}


def build_filing_index_url(cik: str, accession_no: str) -> str:
    """
    Build the URL to the filing's proper index page (the "-index.htm"
    summary page with a Document/Type/Size table), not the bare
    directory listing - the bare listing mixes in metadata files
    (e.g. "-index-headers.html") that aren't actual filing documents.
    """
    folder = accession_no.replace("-", "")
    return f"{EDGAR_ARCHIVES_BASE}/{int(cik)}/{folder}/{accession_no}-index.htm"


def _today() -> str:
    from datetime import date
    return date.today().isoformat()


def _date_days_ago(days: int) -> str:
    from datetime import date, timedelta
    return (date.today() - timedelta(days=days)).isoformat()


if __name__ == "__main__":
    # Quick manual test: python edgar_client.py [days_back]
    import sys
    import json

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    filings = find_recent_424b4_filings(days_back=days)
    print(json.dumps(filings, indent=2))

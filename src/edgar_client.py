"""
edgar_client.py

Discovers newly filed 424B4 (final IPO prospectus) filings on SEC EDGAR,
filters out non-US filers, SPACs, reverse-SPAC/de-SPAC transactions, and
non-operating-company investment products, and locates the matching S-1/S-1A
for the same company so the original filing-range price can be captured
alongside the final offering price.

Requires SEC_EDGAR_USER_AGENT to be set as an environment variable -
SEC requires a descriptive User-Agent with a real contact email on
every request (e.g. "YourName your@email.com"), and will rate-limit or
block requests that don't provide one.
"""

import os
import re
import time
from datetime import date, timedelta

import requests

EDGAR_FULL_TEXT_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

REQUEST_DELAY_SECONDS = 0.15  # keeps us under SEC's ~10 req/sec limit

# SPAC detection must be anchored to the issuer or its cover-page self-description.
# Generic SPAC phrases can appear deep in an operating company's risk factors and
# must not disqualify a legitimate IPO. Include established SPAC franchise names
# that do not contain a generic "acquisition" token (for example Gores Holdings,
# RMG ML Sports Holdings, and GigCapital), while deliberately avoiding a blanket
# "Holdings" exclusion.
SPAC_NAME_PATTERN = re.compile(
    r"\b(?:acquisition|blank check)\b|"
    r"\bcapital\s+(?:corp|partners?)\b|"
    r"\bgores\s+holdings\b|"
    r"\brmg\s+ml\s+sports\s+holdings\b|"
    r"\bgraf\s+industrial\s+corp(?:oration)?\.?(?:\s+[ivx]+)?(?=\W|$)|"
    r"\bgigcapital\d*\b",
    re.IGNORECASE,
)
SPAC_SELF_DESCRIPTION_PATTERNS = [
    re.compile(
        r"\bwe are (?:a|an) (?:newly (?:formed|organized) )?"
        r"(?:blank check|special purpose acquisition) company\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bformed (?:for|with) the (?:sole )?purpose of (?:effecting|entering into) "
        r"(?:an? )?(?:initial )?business combination\b",
        re.IGNORECASE,
    ),
]

# Reverse-SPAC/de-SPAC registrations often use the operating company's post-merger
# name, so issuer-name filtering alone is not enough. These patterns are deliberately
# tied to transaction-completion language near the front of the filing to avoid
# excluding ordinary IPOs that merely discuss SPACs in risk factors or market context.
REVERSE_SPAC_PATTERNS = [
    re.compile(
        r"\b(?:following|upon|after) (?:the )?(?:consummation|completion|closing) "
        r"of (?:the|our) business combination\b.{0,800}\b"
        r"(?:special purpose acquisition company|blank check company|SPAC)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(?:special purpose acquisition company|blank check company|SPAC)\b.{0,800}\b"
        r"(?:following|upon|after) (?:the )?(?:consummation|completion|closing) "
        r"of (?:the|our) business combination\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(?:formerly known as|previously known as)\b.{0,300}\b"
        r"(?:acquisition (?:corp(?:oration)?|company)|blank check company|SPAC)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(?:de[- ]?spac|de[- ]?spac transaction)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdomestication\b.{0,1200}\bbusiness combination\b.{0,1200}\b"
        r"(?:SPAC|special purpose acquisition company|blank check company)\b",
        re.IGNORECASE | re.DOTALL,
    ),
]

# Research Monitor is for operating-company IPOs. These signals are intentionally
# narrow and anchored to issuer names or front-of-prospectus self-descriptions so
# ordinary operating companies are not excluded merely because they mention funds,
# trusts, ETFs, or the Investment Company Act in risk factors.
INVESTMENT_PRODUCT_NAME_PATTERN = re.compile(
    r"\b(?:ETF|ETN)\b|"
    r"\bexchange[- ]traded (?:fund|note)s?\b",
    re.IGNORECASE,
)
INVESTMENT_PRODUCT_SELF_DESCRIPTION_PATTERNS = [
    re.compile(r"\b(?:we are|the fund is|the trust is) an? exchange[- ]traded fund\b", re.IGNORECASE),
    re.compile(r"\b(?:we are|the issuer is) an? exchange[- ]traded note\b", re.IGNORECASE),
    re.compile(r"\b(?:we are|the fund is) an? (?:closed[- ]end|open[- ]end) management investment company\b", re.IGNORECASE),
    re.compile(r"\b(?:we are|the trust is) an? unit investment trust\b", re.IGNORECASE),
    re.compile(r"\b(?:we are|the fund is) an? interval fund\b", re.IGNORECASE),
    re.compile(r"\b(?:we are|the fund is) an? mutual fund\b", re.IGNORECASE),
    re.compile(r"\b(?:we are|the company is) an? business development company\b", re.IGNORECASE),
    re.compile(r"\b(?:the trust|the fund) is (?:a|an) (?:grantor trust|commodity pool|pooled investment vehicle)\b", re.IGNORECASE),
    re.compile(r"\bregistered (?:closed[- ]end|open[- ]end)?\s*investment company under the investment company act of 1940\b", re.IGNORECASE),
]

DIRECT_LISTING_PATTERNS = [
    re.compile(
        r"\b(?:pursuant to|in connection with|through) "
        r"(?:our|a|the) (?:proposed )?direct listing\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bthis (?:registration and )?listing is not an underwritten "
        r"initial public offering\b",
        re.IGNORECASE,
    ),
    # Resale registrations can use Form S-1/S-1A even when no issuer shares are
    # being sold. Keep this deliberately narrow to classic cover-page resale
    # language so ordinary IPOs with a secondary component are not excluded.
    re.compile(
        r"\bthis prospectus relates to (?:the )?(?:offer and sale|resale),? "
        r"from time to time,? by (?:the )?selling "
        r"(?:securityholders|stockholders|shareholders)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    # Some resale-only amendments vary the cover wording while preserving the
    # definitive economics: specifically identified Resale Shares are registered
    # for selling holders and the issuer receives none of the offering proceeds.
    # Requiring all three concepts avoids misclassifying a normal IPO that merely
    # contains a secondary selling-stockholder component.
    re.compile(
        r"\b(?:resale shares|shares registered for resale)\b.{0,2500}\b"
        r"selling (?:securityholders|stockholders|shareholders)\b.{0,1500}\b"
        r"we (?:will|would) not receive any (?:of )?the proceeds\b",
        re.IGNORECASE | re.DOTALL,
    ),
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


def _extract_ticker_from_company_name(value: str):
    """Return the primary ticker from an EFTS display suffix such as '(ACME)'."""
    match = re.search(
        r"\s+\(([A-Z][A-Z0-9.-]{0,9})(?:,\s*[A-Z][A-Z0-9.-]{0,9})*\)\s*$",
        str(value or ""),
    )
    return match.group(1) if match else None


def _clean_company_name(value: str) -> str:
    """Remove EFTS display suffixes such as '(CIK ...)' and '(ACME)'."""
    cleaned = re.sub(
        r"\s*\(CIK\s+\d+\)\s*$", "", str(value or ""), flags=re.IGNORECASE
    ).strip()
    return re.sub(
        r"\s+\([A-Z][A-Z0-9.-]{0,9}(?:,\s*[A-Z][A-Z0-9.-]{0,9})*\)\s*$",
        "",
        cleaned,
    ).strip()


def _request_json(url: str, headers: dict, params: dict = None) -> dict:
    """GET JSON with bounded retries for SEC throttling and transient 5xx errors."""
    last_error = None
    for attempt in range(4):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=20)
            if response.status_code == 429 or response.status_code >= 500:
                raise requests.exceptions.HTTPError(
                    f"SEC returned {response.status_code}", response=response
                )
            response.raise_for_status()
            time.sleep(REQUEST_DELAY_SECONDS)
            return response.json()
        except (requests.exceptions.RequestException, ValueError) as error:
            last_error = error
            if attempt < 3:
                time.sleep(2 ** attempt)
    raise EdgarClientError(f"SEC request failed after retries: {last_error}")

def _find_from_daily_indexes(start_date: str, end_date: str, max_results: int,
                             headers: dict) -> list:
    """Fallback discovery using SEC daily master indexes instead of EFTS."""
    current = date.fromisoformat(start_date)
    final = date.fromisoformat(end_date)
    results = []

    while current <= final and len(results) < max_results:
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
            time.sleep(REQUEST_DELAY_SECONDS)
        except requests.exceptions.RequestException as error:
            print(f"[edgar_client] Daily index unavailable for {current}: {error}")
            current += timedelta(days=1)
            continue

        in_records = False
        for line in response.text.splitlines():
            if line.startswith("-----"):
                in_records = True
                continue
            if not in_records:
                continue
            parts = line.split("|")
            if len(parts) != 5 or parts[2].strip().upper() != "424B4":
                continue
            cik, company_name, form_type, filing_date, filename = parts
            accession_no = filename.rsplit("/", 1)[-1].removesuffix(".txt")
            results.append({
                "company_name": _clean_company_name(company_name),
                "ticker": _extract_ticker_from_company_name(company_name),
                "cik": cik.strip(),
                "accession_no": accession_no,
                "filing_date": filing_date.strip(),
                "form_type": form_type.strip(),
            })
            if len(results) >= max_results:
                break
        current += timedelta(days=1)

    return results


def find_recent_424b4_filings(days_back: int = 1, start_date: str = None,
                                end_date: str = None, max_results: int = 500) -> list:
    """Discover recent 424B4 filings, falling back when SEC EFTS is unstable."""
    headers = _get_headers()
    effective_start = start_date or _date_days_ago(days_back)
    effective_end = end_date or _today()

    results = []
    offset = 0
    page_size = 10

    try:
        while offset < max_results:
            params = {
                "forms": "424B4",
                "dateRange": "custom",
                "startdt": effective_start,
                "enddt": effective_end,
                "from": offset,
            }
            data = _request_json(EDGAR_FULL_TEXT_SEARCH_URL, headers, params)
            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                break

            for hit in hits:
                source = hit.get("_source", {})
                cik = source.get("ciks", [None])[0]
                accession_no = hit.get("_id", "").split(":")[0]
                display_name = source.get("display_names", ["Unknown"])[0]
                results.append({
                    "company_name": _clean_company_name(display_name),
                    "ticker": _extract_ticker_from_company_name(display_name),
                    "cik": cik,
                    "accession_no": accession_no,
                    "filing_date": source.get("file_date"),
                    "form_type": source.get("root_form") or "424B4",
                })

            total = data.get("hits", {}).get("total", {})
            total_available = total.get("value", 0) if isinstance(total, dict) else int(total or 0)
            offset += page_size
            if offset >= total_available:
                break
    except EdgarClientError as error:
        print(f"[edgar_client] EFTS unavailable ({error}); using SEC daily indexes")
        results = _find_from_daily_indexes(
            effective_start, effective_end, max_results, headers
        )

    seen = set()
    deduped = []
    for result in results:
        accession_no = result.get("accession_no")
        if accession_no and accession_no not in seen:
            seen.add(accession_no)
            deduped.append(result)
    return deduped

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


def get_business_location(cik: str) -> str:
    """Return researcher-friendly issuer location from the SEC submissions profile.

    Domestic issuers are rendered as City, ST. Foreign issuers are rendered as
    country because that is the more useful prospect-research grouping.
    """
    headers = _get_headers()
    padded_cik = str(cik).zfill(10)
    url = EDGAR_SUBMISSIONS_URL.format(cik=padded_cik)
    data = _request_json(url, headers)
    address = data.get("addresses", {}).get("business", {}) or {}
    country = str(address.get("countryOfIncorporation") or address.get("country") or "").strip()
    city = str(address.get("city") or "").strip()
    state = str(address.get("stateOrCountry") or address.get("state") or "").strip()
    if country in ("", "US"):
        parts = [part for part in (city, state) if part]
        return ", ".join(parts)
    return country


def get_primary_ticker(cik: str):
    """Return the issuer's first SEC-reported exchange ticker, if present."""
    headers = _get_headers()
    padded_cik = str(cik).zfill(10)
    url = EDGAR_SUBMISSIONS_URL.format(cik=padded_cik)
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    time.sleep(REQUEST_DELAY_SECONDS)
    tickers = data.get("tickers") or []
    return tickers[0] if tickers else None


def check_investment_product_indicators(filing_text: str, company_name: str = "") -> bool:
    """Return True for ETFs, ETNs, funds, trusts, and similar pooled vehicles.

    Detection is conservative: issuer-name matching is limited to explicit ETF/ETN
    language, while broader fund/trust classifications require an affirmative
    self-description near the front of the prospectus.
    """
    if INVESTMENT_PRODUCT_NAME_PATTERN.search(str(company_name or "")):
        return True
    cover_and_summary = str(filing_text or "")[:125000]
    return any(
        pattern.search(cover_and_summary)
        for pattern in INVESTMENT_PRODUCT_SELF_DESCRIPTION_PATTERNS
    )

def check_spac_indicators(filing_text: str, company_name: str = "") -> bool:
    """
    Identify excluded non-operating issuer types handled by the shared IPO gate:
    SPACs, reverse-SPAC/de-SPAC registrations, ETFs, ETNs, and pooled investment
    vehicles. Generic references elsewhere in an operating company's filing are
    not exclusion evidence.
    """
    if check_investment_product_indicators(filing_text, company_name=company_name):
        return True
    if SPAC_NAME_PATTERN.search(str(company_name or "")):
        return True

    cover_and_summary = str(filing_text or "")[:125000]
    return any(pattern.search(cover_and_summary) for pattern in (
        *SPAC_SELF_DESCRIPTION_PATTERNS,
        *REVERSE_SPAC_PATTERNS,
    ))


def check_direct_listing_indicators(filing_text: str) -> bool:
    """Return True for a direct listing or resale registration rather than a primary IPO."""
    # SEC HTML frequently contains non-breaking spaces and other layout whitespace.
    # Normalize it before applying cover-page phrase checks so formatting changes do
    # not allow a known resale-only registration to re-enter the IPO feed.
    cover_and_summary = " ".join(str(filing_text or "").split())[:125000]
    return any(pattern.search(cover_and_summary) for pattern in DIRECT_LISTING_PATTERNS)


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
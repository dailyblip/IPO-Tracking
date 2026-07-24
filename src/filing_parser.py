"""
filing_parser.py

Extracts structured data out of a 424B4 (or S-1) filing's HTML:
- Cover page: company name, ticker, exchange, offering price
- "Principal Stockholders" / beneficial ownership grid: name, shares, %
- "Management" bios (for the Stanford-affiliation check downstream)
- "Underwriting" lock-up terms

SEC prospectus formatting varies a lot between filers, so this locates
sections by heading TEXT (with fuzzy matching on common heading
variants) rather than fixed positions. Expect to refine the regex
patterns here after testing against a handful of real filings - this
is the piece most likely to need iteration.
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup

REQUEST_DELAY_SECONDS = 0.15

# Section headings vary by filer. List common variants, matched
# case-insensitively, in priority order.
OWNERSHIP_HEADING_PATTERNS = [
    r"principal\s+stockholders",
    r"principal\s+shareholders",
    r"security\s+ownership\s+of\s+certain\s+beneficial\s+owners",
    r"beneficial\s+ownership",
]

MANAGEMENT_HEADING_PATTERNS = [
    r"^management$",
    r"executive\s+officers\s+and\s+directors",
    r"directors\s+and\s+executive\s+officers",
]

UNDERWRITING_HEADING_PATTERNS = [
    r"^underwriting$",
    r"lock-?up\s+agreements",
]


class FilingParserError(Exception):
    pass


def _get_headers() -> dict:
    user_agent = os.environ.get("SEC_EDGAR_USER_AGENT")
    if not user_agent:
        raise FilingParserError(
            "SEC_EDGAR_USER_AGENT environment variable is not set."
        )
    return {"User-Agent": user_agent}


def fetch_document(url: str) -> BeautifulSoup:
    """Fetch a filing document and return it as a parsed soup object."""
    headers = _get_headers()
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return BeautifulSoup(response.text, "lxml")


def find_primary_document_url(index_url: str) -> str:
    """
    Given a filing's index page URL, find the primary document - usually
    the largest .htm file, or the one whose "Type" column in the filing
    index table matches the form type (424B4, S-1, etc).
    """
    soup = fetch_document(index_url)
    table = soup.find("table", class_="tableFile") or soup.find("table")
    if table is None:
        raise FilingParserError(f"Could not find document table at {index_url}")

    candidates = []
    for row in table.find_all("tr"):
        link = row.find("a", href=True)
        if link and link["href"].lower().endswith((".htm", ".html")):
            candidates.append(link["href"])

    if not candidates:
        raise FilingParserError(f"No .htm documents found at {index_url}")

    # Heuristic: the primary document is usually the first substantial
    # .htm file listed, and is rarely named things like "ex-" (exhibits).
    main_candidates = [c for c in candidates if "ex" not in c.lower().split("/")[-1][:3]]
    chosen = main_candidates[0] if main_candidates else candidates[0]

    if chosen.startswith("http"):
        return chosen
    if chosen.startswith("/"):
        # Root-relative path (relative to sec.gov's domain root), e.g.
        # "/Archives/edgar/data/.../doc.htm" - this is the common case
        # for EDGAR's filing index tables.
        return f"https://www.sec.gov{chosen}"
    # Bare filename with no leading slash - relative to the index page's
    # own directory.
    base = index_url.rsplit("/", 1)[0]
    return f"{base}/{chosen}"


def _find_section_text(soup: BeautifulSoup, heading_patterns: list, max_chars: int = 20000) -> str:
    """
    Locate a section by scanning heading-like elements (b, strong, h1-h4,
    or bold-styled spans/divs commonly used in EDGAR filings instead of
    real heading tags) for a match against heading_patterns, then
    collect the sibling text following it up to max_chars or the next
    heading of similar prominence.
    """
    heading_regex = re.compile("|".join(heading_patterns), re.IGNORECASE)

    candidates = soup.find_all(["b", "strong", "h1", "h2", "h3", "h4"])
    for tag in candidates:
        text = tag.get_text(strip=True)
        if heading_regex.search(text):
            collected = []
            total_len = 0
            for sibling in tag.find_all_next():
                sibling_text = sibling.get_text(" ", strip=True)
                if sibling.name in ("b", "strong", "h1", "h2", "h3", "h4") and sibling_text:
                    # Stop if we hit what looks like the next major heading
                    if len(sibling_text) < 100 and sibling_text[0:1].isupper():
                        break
                if sibling_text:
                    collected.append(sibling_text)
                    total_len += len(sibling_text)
                if total_len >= max_chars:
                    break
            return " ".join(collected)[:max_chars]

    return ""


def extract_cover_page_data(soup: BeautifulSoup) -> dict:
    """
    Extract company name, ticker, exchange, and offering price from the
    cover page. These usually appear in the first ~2000 characters of
    the document body.
    """
    full_text = soup.get_text(" ", strip=True)
    cover_text = full_text[:5000]

    ticker_match = re.search(
        r"(?:symbol|ticker)[\s\"“]*[:\-]?\s*[\"“]?([A-Z]{1,6})[\"”]?",
        cover_text,
    )
    price_match = re.search(
        r"\$\s?(\d{1,4}(?:\.\d{1,2})?)\s+per\s+share",
        cover_text,
        re.IGNORECASE,
    )
    exchange_match = re.search(
        r"(Nasdaq|New York Stock Exchange|NYSE)",
        cover_text,
        re.IGNORECASE,
    )

    return {
        "ticker": ticker_match.group(1) if ticker_match else None,
        "offering_price": float(price_match.group(1)) if price_match else None,
        "exchange": exchange_match.group(1) if exchange_match else None,
    }


def extract_price_range(soup: BeautifulSoup) -> dict:
    """
    Extract the estimated price range from an S-1/S-1A cover page,
    e.g. "$14.00 and $16.00 per share".
    """
    full_text = soup.get_text(" ", strip=True)
    cover_text = full_text[:5000]

    range_match = re.search(
        r"\$\s?(\d{1,4}(?:\.\d{1,2})?)\s+and\s+\$\s?(\d{1,4}(?:\.\d{1,2})?)\s+per\s+share",
        cover_text,
        re.IGNORECASE,
    )
    if range_match:
        return {
            "range_low": float(range_match.group(1)),
            "range_high": float(range_match.group(2)),
        }
    return {"range_low": None, "range_high": None}


def extract_principal_stockholders(soup: BeautifulSoup) -> list:
    """
    Extract the beneficial ownership grid. Returns a list of dicts:
    {"name": str, "shares": int or None, "percent": float or None}

    Strategy: locate the ownership section heading, then parse the
    first substantial <table> that follows it (these tables reliably
    have a Name column and a Shares/Number column and a % column, in
    varying order and header text).
    """
    heading_regex = re.compile("|".join(OWNERSHIP_HEADING_PATTERNS), re.IGNORECASE)
    heading_tag = None
    for tag in soup.find_all(["b", "strong", "h1", "h2", "h3", "h4"]):
        if heading_regex.search(tag.get_text(strip=True)):
            heading_tag = tag
            break

    if heading_tag is None:
        return []

    table = heading_tag.find_next("table")
    if table is None:
        return []

    rows = table.find_all("tr")
    results = []
    for row in rows:
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        cells = [c for c in cells if c]  # drop empty spacer cells
        if not cells:
            continue

        # Skip header rows (no digits at all in the row)
        if not any(char.isdigit() for char in " ".join(cells)):
            continue

        name = cells[0]
        # Find a cell that looks like a share count (has commas/digits,
        # no % sign, reasonably long number)
        shares = None
        percent = None
        for cell in cells[1:]:
            if "%" in cell:
                pct_match = re.search(r"(\d+(?:\.\d+)?)\s?%", cell)
                if pct_match:
                    percent = float(pct_match.group(1))
            else:
                num_match = re.search(r"([\d,]{4,})", cell)
                if num_match and shares is None:
                    shares = int(num_match.group(1).replace(",", ""))

        if name and (shares is not None or percent is not None):
            results.append({"name": name, "shares": shares, "percent": percent})

    return results


def extract_management_bios(soup: BeautifulSoup) -> dict:
    """
    Extract the Management section text and split it into per-person
    bio chunks keyed by name where possible. Falls back to returning
    the whole section under a single "_full_text" key if per-person
    splitting isn't reliable for this filer's formatting - the grader
    can still substring-search names against that.
    """
    section_text = _find_section_text(soup, MANAGEMENT_HEADING_PATTERNS, max_chars=40000)
    if not section_text:
        return {}

    # Bios often start with "Jane Smith has served as our Chief..." -
    # try splitting on capitalized name-like patterns followed by "has
    # served" / "is our" / "joined" as a light heuristic.
    name_pattern = re.compile(
        r"([A-Z][a-z]+(?:\s[A-Z]\.)?\s[A-Z][a-z]+)\s+(?:has served|is our|joined|has been)"
    )
    matches = list(name_pattern.finditer(section_text))

    if not matches:
        return {"_full_text": section_text}

    bios = {}
    for i, match in enumerate(matches):
        name = match.group(1)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section_text)
        bios[name] = section_text[start:end].strip()

    bios["_full_text"] = section_text
    return bios


def extract_lockup_info(soup: BeautifulSoup) -> dict:
    """
    Extract lock-up language from the Underwriting section. Returns the
    raw matched text plus a best-effort parsed duration in days, where
    the standard boilerplate ("180 days") is detected.
    """
    section_text = _find_section_text(soup, UNDERWRITING_HEADING_PATTERNS, max_chars=15000)
    if not section_text:
        return {"raw_text": None, "duration_days": None}

    lockup_sentences = [
        s for s in re.split(r"(?<=[.])\s+", section_text)
        if "lock-up" in s.lower() or "lockup" in s.lower()
    ]
    raw_text = " ".join(lockup_sentences[:5]) if lockup_sentences else None

    duration_match = re.search(r"(\d{2,3})\s+days", raw_text or "")
    duration_days = int(duration_match.group(1)) if duration_match else None

    return {"raw_text": raw_text, "duration_days": duration_days}


def parse_filing(document_url: str, is_range_filing: bool = False) -> dict:
    """
    Top-level entry point: fetch a filing document and extract
    everything main.py needs. Set is_range_filing=True when parsing an
    S-1/S-1A (returns range_low/range_high instead of offering_price).
    """
    soup = fetch_document(document_url)

    result = {
        "cover_page": extract_cover_page_data(soup),
        "principal_stockholders": extract_principal_stockholders(soup),
        "management_bios": extract_management_bios(soup),
        "lockup_info": extract_lockup_info(soup),
    }

    if is_range_filing:
        result["price_range"] = extract_price_range(soup)

    return result


if __name__ == "__main__":
    # Quick manual test: python filing_parser.py <document_url>
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python filing_parser.py <document_url>")
        sys.exit(1)

    parsed = parse_filing(sys.argv[1])
    print(json.dumps(parsed, indent=2, default=str))

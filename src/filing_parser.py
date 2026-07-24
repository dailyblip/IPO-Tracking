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


def find_primary_document_url(index_url: str, expected_form_types: list = None) -> str:
    """
    Given a filing's "-index.htm" page URL, find the primary document.
    Prefers the row whose "Type" column matches one of
    expected_form_types (e.g. ["424B4"] or ["S-1", "S-1/A"]) - EDGAR's
    index table reliably has this column, which is a much more precise
    signal than guessing from the filename. Falls back to the first
    non-exhibit, non-metadata .htm file if no type match is found.
    """
    soup = fetch_document(index_url)
    table = soup.find("table", class_="tableFile") or soup.find("table")
    if table is None:
        raise FilingParserError(f"Could not find document table at {index_url}")

    candidates = []  # (href, matched_type_bool)
    for row in table.find_all("tr"):
        link = row.find("a", href=True)
        if not (link and link["href"].lower().endswith((".htm", ".html"))):
            continue
        cell_texts = [c.get_text(strip=True) for c in row.find_all("td")]
        matched_type = bool(expected_form_types) and any(
            ft.upper() == cell.upper() for ft in expected_form_types for cell in cell_texts
        )
        candidates.append((link["href"], matched_type))

    if not candidates:
        raise FilingParserError(f"No .htm documents found at {index_url}")

    type_matches = [href for href, matched in candidates if matched]
    if type_matches:
        chosen = type_matches[0]
    else:
        # Fall back: skip exhibits ("ex-...") and EDGAR metadata files
        # (the "-index.htm"/"-index-headers.html" pages link to
        # themselves in this same table).
        non_exhibit = [
            href for href, _ in candidates
            if "ex" not in href.lower().split("/")[-1][:3]
            and "-index" not in href.lower()
        ]
        chosen = non_exhibit[0] if non_exhibit else candidates[0][0]

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


def _looks_bold(tag) -> bool:
    """Check for inline CSS bold styling, since many EDGAR filings use
    styled spans/divs for headings instead of semantic <b>/<strong> tags."""
    if tag.name in ("b", "strong"):
        return True
    style = tag.get("style", "") or ""
    if re.search(r"font-weight\s*:\s*(bold|[6-9]00)", style, re.IGNORECASE):
        return True
    return False


def _find_heading_tag(soup: BeautifulSoup, heading_patterns: list):
    """
    Locate a heading-like element matching heading_patterns. Tries, in
    order of preference:
    1. Real semantic tags (b, strong, h1-h4) with matching text - the
       fast path, works when a filer uses semantic markup.
    2. Any short element with inline bold styling whose own text
       matches - common in filings generated by compliance/typesetting
       software that styles spans/divs instead of using bold tags.
    3. Short, ALL-CAPS text matching the pattern with no styling at all
       - some prospectuses render headings as plain caps text.
    Returns None if nothing matches any of the three passes.
    """
    heading_regex = re.compile("|".join(heading_patterns), re.IGNORECASE)

    for tag in soup.find_all(["b", "strong", "h1", "h2", "h3", "h4"]):
        text = tag.get_text(strip=True)
        if text and len(text) < 150 and heading_regex.search(text):
            return tag

    for tag in soup.find_all(["p", "span", "div", "font", "td", "th"]):
        # Skip large wrapper containers - only interested in
        # paragraph/cell-level elements with no block-level children.
        if tag.find(["p", "div", "table"]):
            continue
        text = tag.get_text(strip=True)
        if not text or len(text) > 150 or not heading_regex.search(text):
            continue
        if _looks_bold(tag) or text.isupper():
            return tag

    return None


def keyword_present_in_text(soup: BeautifulSoup, patterns: list) -> bool:
    """
    Diagnostic helper: checks whether any heading pattern appears
    ANYWHERE in the document's raw text, regardless of tag structure.
    Used to distinguish "section exists but our heading detection
    missed it" from "section genuinely isn't in this document."
    """
    heading_regex = re.compile("|".join(patterns), re.IGNORECASE)
    full_text = soup.get_text(" ", strip=True)
    return bool(heading_regex.search(full_text))


def _find_section_text(soup: BeautifulSoup, heading_patterns: list, max_chars: int = 20000) -> str:
    """
    Locate a section via _find_heading_tag, then collect the sibling
    text following it up to max_chars or the next heading of similar
    prominence.
    """
    heading_tag = _find_heading_tag(soup, heading_patterns)
    if heading_tag is None:
        return ""

    collected = []
    total_len = 0
    for sibling in heading_tag.find_all_next():
        sibling_text = sibling.get_text(" ", strip=True)
        is_next_heading = (
            sibling_text
            and len(sibling_text) < 150
            and (_looks_bold(sibling) or sibling_text.isupper())
            and sibling.find(["p", "div", "table"]) is None
        )
        if is_next_heading and total_len > 200:
            # Only treat as a stopping point once we've already
            # collected some content, so we don't immediately bail on
            # a heading's own nested formatting.
            break
        if sibling_text:
            collected.append(sibling_text)
            total_len += len(sibling_text)
        if total_len >= max_chars:
            break
    return " ".join(collected)[:max_chars]


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
    heading_tag = _find_heading_tag(soup, OWNERSHIP_HEADING_PATTERNS)
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
        "diagnostics": {
            "ownership_keyword_present": keyword_present_in_text(soup, OWNERSHIP_HEADING_PATTERNS),
            "management_keyword_present": keyword_present_in_text(soup, MANAGEMENT_HEADING_PATTERNS),
            "underwriting_keyword_present": keyword_present_in_text(soup, UNDERWRITING_HEADING_PATTERNS),
            "page_text_length": len(soup.get_text(strip=True)),
        },
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

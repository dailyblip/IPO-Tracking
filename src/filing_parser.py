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

from ownership_parser import extract_rich_stockholders
from lockup_parser import extract_holder_lockup_info

REQUEST_DELAY_SECONDS = 0.15

# Section headings vary by filer. List common variants, matched
# case-insensitively, in priority order.
OWNERSHIP_HEADING_PATTERNS = [
    r"principal\s+(?:and\s+selling\s+)?stockholders",
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
    """Check the element and inline descendants for bold styling.

    EDGAR generators often split a visual heading across several styled
    font or span children while leaving the wrapping paragraph unstyled.
    """
    candidates = [tag, *tag.find_all(["b", "strong", "span", "font"])]
    for candidate in candidates:
        if candidate.name in ("b", "strong"):
            return True
        style = candidate.get("style", "") or ""
        if re.search(r"font-weight\s*:\s*(bold|[6-9]00)", style, re.IGNORECASE):
            return True
    return False

def _find_heading_tags(soup: BeautifulSoup, heading_patterns: list) -> list:
    """Return every plausible heading; SEC tables of contents repeat names."""
    heading_regex = re.compile("|".join(heading_patterns), re.IGNORECASE)
    matches = []

    for tag in soup.find_all(["b", "strong", "h1", "h2", "h3", "h4"]):
        text = tag.get_text(strip=True)
        if text and len(text) < 150 and heading_regex.search(text):
            matches.append(tag)

    for tag in soup.find_all(["p", "span", "div", "font", "td", "th"]):
        if tag.find(["p", "div", "table"]):
            continue
        text = tag.get_text(strip=True)
        if not text or len(text) > 150 or not heading_regex.search(text):
            continue
        if _looks_bold(tag) or text.isupper():
            matches.append(tag)

    return matches


def _find_heading_tag(soup: BeautifulSoup, heading_patterns: list):
    """Return the first plausible heading for text-only section extraction."""
    matches = _find_heading_tags(soup, heading_patterns)
    return matches[0] if matches else None

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
    cover_text = full_text[:100000]

    ticker_match = re.search(
        r"(?:symbol|ticker)[\s\"“]*[:\-]?\s*[\"“]?([A-Z]{1,6})[\"”]?",
        cover_text,
    )
    price_patterns = [
        r"initial public offering price(?:\s+per\s+share)?"
        r"\s*(?:is|of|:)?\s*\$\s*(\d{1,4}(?:\.\d{1,2})?)",
        r"public offering price(?:\s+per\s+share)?"
        r"\s*(?:is|of|:)?\s*\$\s*(\d{1,4}(?:\.\d{1,2})?)",
        r"price\s+to\s+(?:the\s+)?public(?:\s+per\s+share)?\s*[:\-]?\s*\$\s*(\d{1,4}(?:\.\d{1,2})?)",
        r"offering\s+price\s+per\s+share\s*[:\-]?\s*\$\s*(\d{1,4}(?:\.\d{1,2})?)",
        r"\$\s*(\d{1,4}(?:\.\d{1,2})?)\s+per\s+(?:ordinary\s+|class\s+[ab]\s+)?share",
    ]
    price_match = next(
        (
            match
            for pattern in price_patterns
            if (match := re.search(pattern, cover_text, re.IGNORECASE))
        ),
        None,
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


def extract_principal_office_location(soup: BeautifulSoup):
    """Extract principal executive office location from the filing cover page.

    Prefer filing disclosure to SEC submissions metadata because the latter may
    reflect a registered/business address that is not the research-relevant HQ.
    Returns a compact ``City, ST`` for US addresses, otherwise None.
    """
    cover_text = soup.get_text(" ", strip=True)[:100000]
    # Registration/prospectus covers often put the address immediately before
    # the parenthetical label rather than in a sentence saying "located at".
    label = re.search(r"\(Address[^)]*principal executive offices\)", cover_text, re.I)
    if label:
        preceding = cover_text[max(0, label.start()-600):label.start()]
        address_matches = re.findall(r"\b([A-Za-z][A-Za-z .'-]{1,50}),\s*([A-Z]{2})\s+\d{5}(?:-\d{4})?", preceding)
        if address_matches:
            city, state = address_matches[-1]
            city = " ".join(city.split()).strip(" ,")
            if city:
                return f"{city}, {state.upper()}"
    patterns = [
        r"principal executive offices? (?:are|is) located at [^.;]{0,220}?\b([A-Za-z .'-]{2,60}),\s*([A-Z]{2})\s+\d{5}(?:-\d{4})?",
        r"principal executive offices?[^.;]{0,220}?\b([A-Za-z .'-]{2,60}),\s*([A-Z]{2})\s+\d{5}(?:-\d{4})?",
        r"address of principal executive offices?[^.;]{0,220}?\b([A-Za-z .'-]{2,60}),\s*([A-Z]{2})\s+\d{5}(?:-\d{4})?",
    ]
    for pattern in patterns:
        match = re.search(pattern, cover_text, re.I)
        if match:
            city = " ".join(match.group(1).split()).strip(" ,")
            state = match.group(2).upper()
            if city and state:
                return f"{city}, {state}"
    return None



def extract_price_range(soup: BeautifulSoup) -> dict:
    """
    Extract the estimated price range from an S-1/S-1A cover page,
    e.g. "$14.00 and $16.00 per share".
    """
    full_text = soup.get_text(" ", strip=True)
    cover_text = full_text[:30000]

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


def _share_int(value):
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def extract_offering_terms(soup: BeautifulSoup) -> dict:
    """Extract base IPO share count with source/confidence and primary/secondary split.

    A prospectus contains many share counts (shares outstanding, equity-plan reserves,
    beneficial ownership, greenshoes). Research-grade extraction must never choose a
    generic later share count merely because it matches ``N shares of common stock``.
    We rank only cover/title and explicit offering constructions, and exclude the
    underwriters' option from base IPO size.
    """
    text = soup.get_text(" ", strip=True)
    cover = text[:50000]

    primary = secondary = total = None
    sources = []
    confidence = "Unresolved"
    conflict = False

    # Most explicit construction: issuer block + selling-stockholder block.
    combined_patterns = [
        r"we\s+(?:are|will\s+be)\s+offering\s+([\d,]{4,})\s+shares[^.]{0,1600}?"
        r"selling\s+stockholders?[^.]{0,900}?(?:are\s+offering|are\s+selling|will\s+sell|offer)"
        r"(?:\s+an\s+additional)?\s+([\d,]{4,})\s+shares",
        r"we\s+(?:are|will\s+be)\s+offering\s+([\d,]{4,})\s+shares[^.]{0,1600}?"
        r"selling\s+shareholders?[^.]{0,900}?(?:are\s+offering|are\s+selling|will\s+sell|offer)"
        r"(?:\s+an\s+additional)?\s+([\d,]{4,})\s+shares",
    ]
    for pattern in combined_patterns:
        match = re.search(pattern, cover, re.I)
        if match:
            primary = _share_int(match.group(1))
            secondary = _share_int(match.group(2))
            if primary is not None and secondary is not None:
                total = primary + secondary
                sources.append("explicit issuer + selling-holder cover blocks")
                confidence = "High"
                break

    # Common THE OFFERING table construction. Use only explicit 'offered by' labels.
    if primary is None:
        m = re.search(
            r"(?:common\s+stock|shares?)\s+offered\s+by\s+(?:us|the\s+company)\s*[:|]?\s*([\d,]{4,})\s+shares",
            cover, re.I,
        )
        if m:
            primary = _share_int(m.group(1))
    if secondary is None:
        m = re.search(
            r"(?:common\s+stock|shares?)\s+offered\s+by\s+(?:the\s+)?selling\s+(?:stockholders|shareholders)\s*[:|]?\s*([\d,]{4,})\s+shares",
            cover, re.I,
        )
        if m:
            secondary = _share_int(m.group(1))
    if total is None and primary is not None and secondary is not None:
        total = primary + secondary
        sources.append("THE OFFERING primary + secondary rows")
        confidence = "High"

    # Explicit total statement/title. These are much safer than a generic share-count match.
    total_candidates = []
    explicit_patterns = [
        (r"initial\s+public\s+offering\s+of\s+([\d,]{4,})\s+shares", "explicit initial-public-offering total"),
        (r"(?:preliminary\s+)?prospectus\s+([\d,]{4,})\s+shares\s+(?:of\s+)?(?:class\s+[a-z]\s+)?common\s+stock", "prospectus cover title"),
        (r"\b([\d,]{4,})\s+shares\s+(?:of\s+)?(?:class\s+[a-z]\s+)?common\s+stock\s+this\s+is\b", "cover share title"),
    ]
    for pattern, label in explicit_patterns:
        for match in re.finditer(pattern, cover, re.I):
            value = _share_int(match.group(1))
            if value:
                total_candidates.append((match.start(), value, label))

    # Some EDGAR covers render title and narrative as separate blocks:
    # "17,000,000 Shares Common Stock This is ... initial public offering ..."
    for match in re.finditer(r"\b([\d,]{4,})\s+shares\s+(?:of\s+)?(?:class\s+[a-z]\s+)?common\s+stock\b", cover[:20000], re.I):
        nearby = cover[max(0, match.start()-250):min(len(cover), match.end()+650)].lower()
        if "initial public offering" in nearby and "outstanding" not in nearby:
            value = _share_int(match.group(1))
            if value:
                total_candidates.append((match.start(), value, "cover title adjacent to IPO statement"))

    if total_candidates:
        total_candidates.sort(key=lambda item: item[0])
        _, explicit_total, label = total_candidates[0]
        if total is None:
            total = explicit_total
            sources.append(label)
            confidence = "High"
        elif total != explicit_total:
            conflict = True
            sources.append(f"conflict with {label} ({explicit_total:,} shares)")
        else:
            sources.append(label)

    # Issuer-only offering. Safe only when the cover does not identify selling holders
    # participating in the base offering.
    if total is None:
        issuer_only = re.search(r"\bwe\s+(?:are|will\s+be)\s+offering\s+([\d,]{4,})\s+shares\b", cover[:25000], re.I)
        selling_language = re.search(r"selling\s+(?:stockholders|shareholders)[^.]{0,900}?(?:offering|selling|sell)\s+(?:an\s+additional\s+)?[\d,]{4,}\s+shares", cover[:30000], re.I)
        if issuer_only and not selling_language:
            primary = _share_int(issuer_only.group(1))
            total = primary
            sources.append("explicit issuer-only cover statement")
            confidence = "High"

    # Last-resort pattern is deliberately restricted to the first 15k and requires
    # nearby IPO language. It is flagged Medium so QC can surface it for review.
    if total is None:
        for match in re.finditer(r"\boffering\s+([\d,]{4,})\s+shares\b", cover[:15000], re.I):
            nearby = cover[max(0, match.start()-500):min(len(cover), match.end()+500)].lower()
            if "initial public offering" in nearby and "outstanding" not in nearby:
                total = _share_int(match.group(1))
                sources.append("context-limited offering-share fallback")
                confidence = "Medium"
                break

    return {
        "total_shares": total,
        "primary_shares": primary,
        "secondary_shares": secondary,
        "source": "; ".join(sources) if sources else None,
        "confidence": confidence,
        "conflict": conflict,
    }


def extract_offering_size(soup: BeautifulSoup) -> int:
    """Backward-compatible base-offering share count."""
    return extract_offering_terms(soup).get("total_shares")


OWNERSHIP_TABLE_HEADER_KEYWORDS = [
    "beneficially owned", "beneficial owner", "shares owned", "shares beneficially",
    "percent of class", "percentage of class", "percent owned", "percentage owned",
    "name of beneficial owner",
]


def _table_header_looks_like_ownership(table) -> bool:
    """
    Checks the table's first eight rows (where grouped headers can span rows)
    for actual ownership-grid language. This is a much sharper filter
    than checking individual data rows - a financial highlights table
    (e.g. "Revenues", "Net loss", "Adjusted EBITDA") can superficially
    resemble a person/number grid at the row level, but its header
    won't contain ownership-specific phrasing the way a real
    "Principal Stockholders" table's header does.
    """
    # Grouped Before/After Offering headers often span several rows.
    rows = table.find_all("tr")[:8]
    header_text = " ".join(
        c.get_text(" ", strip=True) for row in rows for c in row.find_all(["td", "th"])
    ).lower()
    return any(keyword in header_text for keyword in OWNERSHIP_TABLE_HEADER_KEYWORDS)


def extract_principal_stockholders(soup: BeautifulSoup) -> list:
    """
    Extract the beneficial ownership grid. Returns a list of dicts:
    {"name": str, "shares": int or None, "percent": float or None}

    Strategy: locate every ownership heading candidate, then check up to
    12 tables after each one. Prospectuses often repeat the heading in a
    table of contents long before the actual section, split visual headings
    across styled inline elements, or continue a wide ownership grid in a
    second table. A table is accepted only when its header contains actual
    ownership-grid language and it yields plausible named rows.
    """
    heading_tags = _find_heading_tags(soup, OWNERSHIP_HEADING_PATTERNS)
    if not heading_tags:
        return []

    results = []
    seen_names = set()
    seen_tables = set()
    for heading_tag in heading_tags:
        # Inspect tables after every match; the first is often the contents page.
        candidate_tables = heading_tag.find_all_next("table", limit=12)

        for table in candidate_tables:
            table_identity = id(table)
            if table_identity in seen_tables:
                continue
            seen_tables.add(table_identity)
            if not _table_header_looks_like_ownership(table):
                continue

            table_results = []
            for row in table.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
                cells = [c for c in cells if c]  # drop empty spacer cells
                if not cells:
                    continue

                # Skip header rows (no digits at all in the row)
                if not any(char.isdigit() for char in " ".join(cells)):
                    continue

                name = cells[0]
                # A real holder name has at least one letter - guards
                # against a misfired match where the first cell is
                # actually a price, share count, or other numeric value.
                if not any(ch.isalpha() for ch in name):
                    continue

                shares = None
                percent = None
                for cell in cells[1:]:
                    if "%" in cell:
                        pct_match = re.search(r"(\d+(?:\.\d+)?)\s?%", cell)
                        if pct_match:
                            percent = float(pct_match.group(1))
                    elif shares is None:
                        # Ownership tables can contain legitimate holdings below
                        # 1,000 shares. Requiring the entire cell to be numeric
                        # avoids confusing footnote markers with share counts.
                        num_match = re.fullmatch(r"\s*([\d,]+)\s*", cell)
                        if num_match:
                            shares = int(num_match.group(1).replace(",", ""))

                if name and (shares is not None or percent is not None):
                    table_results.append(
                        {"name": name, "shares": shares, "percent": percent}
                    )

            # Wide SEC ownership grids are sometimes split into consecutive
            # tables. Combine every accepted grid while deduplicating holders
            # repeated in a continuation.
            for holder in table_results:
                holder_key = " ".join(holder["name"].lower().split())
                if holder_key in seen_names:
                    continue
                seen_names.add(holder_key)
                results.append(holder)

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
    """Extract structured holder-facing lock-up terms from the full prospectus."""
    full_text = soup.get_text(" ", strip=True)
    return extract_holder_lockup_info(full_text)


def parse_filing(document_url: str, is_range_filing: bool = False) -> dict:
    """
    Top-level entry point: fetch a filing document and extract
    everything main.py needs. Set is_range_filing=True when parsing an
    S-1/S-1A (returns range_low/range_high instead of offering_price).
    """
    soup = fetch_document(document_url)

    cover_page_data = extract_cover_page_data(soup)
    offering_terms = extract_offering_terms(soup)
    cover_page_data["offering_size_shares"] = offering_terms.get("total_shares")
    cover_page_data["primary_offering_shares"] = offering_terms.get("primary_shares")
    cover_page_data["secondary_offering_shares"] = offering_terms.get("secondary_shares")
    cover_page_data["offering_size_source"] = offering_terms.get("source")
    cover_page_data["offering_size_confidence"] = offering_terms.get("confidence")
    cover_page_data["offering_size_conflict"] = offering_terms.get("conflict", False)

    result = {
        "cover_page": cover_page_data,
        "principal_office_location": extract_principal_office_location(soup),
        "principal_stockholders": extract_rich_stockholders(soup) or extract_principal_stockholders(soup),
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

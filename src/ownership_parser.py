"""Structured extraction for wide SEC beneficial-ownership tables.

The parser is deliberately conservative: it preserves before/offered/after
columns only when the table headers identify their meaning. Unknown fields stay
None rather than being guessed from position alone.
"""
from __future__ import annotations

import re

OWNERSHIP_WORDS = (
    "beneficially owned", "beneficial owner", "shares owned", "shares beneficially",
    "percent of class", "percentage of class", "percent owned", "percentage owned",
    "name of beneficial owner", "principal stockholder", "principal shareholder",
)

# Common prospectus section labels that can appear inside or adjacent to ownership
# tables. These are document structure, never beneficial-owner identities. Keep
# this list deliberately explicit rather than rejecting all-uppercase names,
# because legitimate fund and corporate owner names may be uppercase in SEC HTML.
_DOCUMENT_SECTION_HEADINGS = {
    "description of capital stock",
    "shares eligible for future sale",
    "material u.s. federal income tax considerations",
    "material us federal income tax considerations",
    "material u.s. federal income tax consequences to non-u.s. holders",
    "material us federal income tax consequences to non-us holders",
    "legal matters",
    "risk factors",
    "use of proceeds",
    "dividend policy",
    "capitalization",
    "dilution",
    "executive compensation",
    "principal stockholders",
    "principal shareholders",
    "certain relationships and related party transactions",
    "certain relationships and related transactions",
    "certain relationships and related person transactions",
    "forward-looking statements",
    "a letter from our ceo",
    "letter from our ceo",
    "business",
    "experts",
    "where you can find more information",
    "where you can find additional information",
}


def _clean(text):
    value = " ".join(str(text or "").replace("\xa0", " ").split())
    # SEC tables often use dot leaders between holder labels and numeric columns.
    # They are presentation artifacts, never part of a person's/entity's name.
    value = re.sub(r"\s*\.{3,}\s*$", "", value)
    return value.strip()


def canonical_holder_name(value):
    """Canonical identity key for holder deduplication, without guessing identity."""
    value = _clean(value)
    value = re.sub(r"(?:\s*\(\d+[a-z]?\))+$", "", value, flags=re.I)
    value = re.sub(r"[†‡*]+$", "", value).strip()
    value = re.sub(r"\s*\.{2,}\s*", " ", value)
    return " ".join(value.lower().split())


def looks_like_document_heading(value):
    """Return True only for strong prospectus-section labels, not uppercase generally."""
    normalized = canonical_holder_name(value)
    if not normalized:
        return False
    if normalized in _DOCUMENT_SECTION_HEADINGS:
        return True
    # SEC prospectuses frequently append a parenthetical to the Underwriting
    # heading (for example, "UNDERWRITING (CONFLICTS OF INTEREST)"). Avoid a
    # generic startswith check so an actual owner such as "Underwriting Capital
    # Partners LLC" remains eligible.
    return normalized in {"underwriting", "underwriters"} or normalized.startswith("underwriting (")


def _expand_row(row):
    out = []
    for cell in row.find_all(["td", "th"], recursive=False):
        text = _clean(cell.get_text(" ", strip=True))
        try:
            span = max(1, int(cell.get("colspan", 1)))
        except (TypeError, ValueError):
            span = 1
        out.extend([text] * span)
    return out


def _matrix(table):
    rows = [_expand_row(row) for row in table.find_all("tr")]
    width = max((len(r) for r in rows), default=0)
    return [r + [""] * (width - len(r)) for r in rows]


def _looks_like_ownership(table):
    text = " ".join(_clean(r.get_text(" ", strip=True)).lower() for r in table.find_all("tr")[:10])
    return any(word in text for word in OWNERSHIP_WORDS)


def _numeric(text):
    value = _clean(text)
    if not value or value in {"—", "-", "*", "**"}:
        return None
    value = re.sub(r"\(\d+[a-z]?\)", "", value, flags=re.I).strip()
    value = re.sub(r"[†‡*]+$", "", value).strip()
    match = re.fullmatch(r"\$?\s*([\d,]+(?:\.\d+)?)\s*%?", value)
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    return int(number) if number.is_integer() else number


def _percent(text):
    value = _clean(text)
    if not value:
        return None
    match = re.search(r"([\d,.]+)\s*%", value)
    if match:
        return float(match.group(1).replace(",", ""))
    return None


def _composite_headers(matrix):
    header_rows = []
    for row in matrix[:10]:
        has_number = any(_numeric(c) is not None or _percent(c) is not None for c in row[1:])
        first = next((c for c in row if c), "")
        looks_holder = bool(first and has_number and not re.search(
            r"beneficial|before|after|offering|owned|percent|number|shares|name", first, re.I
        ))
        if looks_holder and header_rows:
            break
        header_rows.append(row)
    width = max((len(r) for r in matrix), default=0)
    headers = []
    for i in range(width):
        parts = []
        for row in header_rows:
            part = _clean(row[i] if i < len(row) else "")
            if part and (not parts or parts[-1].lower() != part.lower()):
                parts.append(part)
        headers.append(" ".join(parts).lower())
    return headers, len(header_rows)


def _kind(header):
    h = header.lower()
    is_pct = "%" in h or "percent" in h or "percentage" in h
    if re.search(r"shares?\s+(?:being\s+)?(?:offered|sold)|offered\s+shares|secondary", h):
        return "shares_sold"
    if re.search(r"before|prior to|pre-offering|pre offering", h):
        return "percent_before" if is_pct else "shares_before"
    if re.search(r"after|following|post-offering|post offering", h):
        return "percent_after" if is_pct else "shares_after"
    if is_pct and re.search(r"beneficial|owned|class", h):
        return "percent"
    if re.search(r"number|shares", h) and re.search(r"beneficial|owned", h):
        return "shares"
    return None


def _name_from_row(row):
    for cell in row:
        text = _clean(cell)
        if not text:
            continue
        if any(ch.isalpha() for ch in text) and not re.search(
            r"beneficial|before|after|offering|percent|percentage|number of|shares owned", text, re.I
        ):
            if looks_like_document_heading(text):
                return None
            return text
        if _numeric(text) is not None or _percent(text) is not None:
            break
    return None


def parse_ownership_table(table):
    """Return rich holder dictionaries from one ownership table."""
    if not _looks_like_ownership(table):
        return []
    matrix = _matrix(table)
    headers, start = _composite_headers(matrix)
    kinds = [_kind(h) for h in headers]
    results = []
    for row in matrix[start:]:
        name = _name_from_row(row)
        if not name:
            continue
        data = {
            "name": name,
            "shares": None,
            "percent": None,
            "shares_before": None,
            "percent_before": None,
            "shares_sold": None,
            "shares_after": None,
            "percent_after": None,
        }
        for i, cell in enumerate(row):
            kind = kinds[i] if i < len(kinds) else None
            if not kind:
                continue
            if kind.startswith("percent"):
                value = _percent(cell)
                if value is None and "%" in headers[i]:
                    n = _numeric(cell)
                    value = float(n) if n is not None else None
            else:
                value = _numeric(cell)
            if value is not None and data.get(kind) is None:
                data[kind] = value
        if all(data[k] is None for k in ("shares_before", "shares_sold", "shares_after", "shares")):
            numeric = [_numeric(c) for c in row[1:] if _numeric(c) is not None]
            if len(numeric) == 1:
                data["shares"] = numeric[0]
        if data["percent_after"] is None and data["percent"] is not None:
            data["percent_after"] = data["percent"]
        if data["shares_after"] is None and data["shares"] is not None:
            data["shares_after"] = data["shares"]
        if any(data[k] is not None for k in ("shares_before", "shares_sold", "shares_after", "percent_before", "percent_after")):
            results.append(data)
    return results


def extract_rich_stockholders(soup):
    """Scan ownership-like tables and merge repeated holder rows."""
    merged = {}
    order = []
    for table in soup.find_all("table"):
        if not _looks_like_ownership(table):
            continue
        for holder in parse_ownership_table(table):
            if looks_like_document_heading(holder.get("name")):
                continue
            key = canonical_holder_name(holder["name"])
            if key not in merged:
                merged[key] = holder
                order.append(key)
            else:
                for field, value in holder.items():
                    if field != "name" and merged[key].get(field) is None and value is not None:
                        merged[key][field] = value
    return [merged[key] for key in order]

# Integration workflow trigger marker.

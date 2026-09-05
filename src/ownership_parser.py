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
    "description of indebtedness",
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
    "controlled company",
    "conflicts of interest",
    "experts",
    "where you can find more information",
    "where you can find additional information",
}

# Some SEC section headings append a holder-class qualifier. Limit prefix matching
# to well-known tax-section labels rather than broadly rejecting long uppercase
# text, because legitimate holder names can also be uppercase.
_DOCUMENT_SECTION_HEADING_PREFIXES = (
    "material u.s. federal income tax considerations to ",
    "material us federal income tax considerations to ",
    "material u.s. federal income tax considerations for ",
    "material us federal income tax considerations for ",
    "material u.s. federal income tax consequences to ",
    "material us federal income tax consequences to ",
    "material u.s. federal income tax consequences for ",
    "material us federal income tax consequences for ",
)

_PERCENT_MARKERS = {"%", "percent", "percentage"}
_SHARE_TO_PERCENT = {
    "shares": "percent",
    "shares_before": "percent_before",
    "shares_after": "percent_after",
}
_SHARE_CLASS_RE = re.compile(
    r"\bclass\s+([a-z0-9]+)\s+(?:common\s+)?(?:stock|shares?)\b", re.I
)


def _clean(text):
    value = " ".join(str(text or "").replace("\xa0", " ").split())
    # SEC tables often use dot leaders between holder labels and numeric columns.
    # They are presentation artifacts, never part of a person's/entity's name.
    value = re.sub(r"\s*\.{3,}\s*$", "", value)
    return value.strip()


def _clean_holder_label(value):
    """Remove SEC footnote/presentation artifacts without rewriting the identity."""
    value = _clean(value)
    # Numeric parentheticals at the end of ownership-table labels are SEC footnote
    # references, not part of the person/entity name. Some filings leave a lone
    # presentation dot after the marker (for example ``AA&D Holdings, LP (1) .``).
    value = re.sub(
        r"(?:\s*\(\d+[a-z]?\))+(?:\s*\.)?\s*$",
        "",
        value,
        flags=re.I,
    )
    value = re.sub(r"[†‡*]+$", "", value).strip()
    return value


def canonical_holder_name(value):
    """Canonical identity key for holder deduplication, without guessing identity."""
    value = _clean_holder_label(value)
    value = re.sub(r"\s*\.{2,}\s*", " ", value)
    return " ".join(value.lower().split())


def looks_like_document_heading(value):
    """Return True only for strong prospectus-section labels, not uppercase generally."""
    normalized = canonical_holder_name(value)
    if not normalized:
        return False
    if normalized in _DOCUMENT_SECTION_HEADINGS:
        return True
    if any(normalized.startswith(prefix) for prefix in _DOCUMENT_SECTION_HEADING_PREFIXES):
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
    """Expand SEC table colspans and rowspans into a rectangular text grid."""
    rows = []
    active_rowspans = {}
    for table_row in table.find_all("tr"):
        values = {}
        next_rowspans = {}

        for column, (text, remaining) in active_rowspans.items():
            values[column] = text
            if remaining > 1:
                next_rowspans[column] = (text, remaining - 1)

        column = 0
        for cell in table_row.find_all(["td", "th"], recursive=False):
            while column in values:
                column += 1

            text = _clean(cell.get_text(" ", strip=True))
            try:
                colspan = max(1, int(cell.get("colspan", 1)))
            except (TypeError, ValueError):
                colspan = 1
            try:
                rowspan = max(1, int(cell.get("rowspan", 1)))
            except (TypeError, ValueError):
                rowspan = 1

            placed = 0
            while placed < colspan:
                while column in values:
                    column += 1
                values[column] = text
                if rowspan > 1:
                    next_rowspans[column] = (text, rowspan - 1)
                column += 1
                placed += 1

        active_rowspans = next_rowspans
        width = max(values, default=-1) + 1
        rows.append([values.get(index, "") for index in range(width)])

    width = max((len(row) for row in rows), default=0)
    return [row + [""] * (width - len(row)) for row in rows]


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


def _explicit_percent(cells, index):
    """Return a percentage only when SEC table markup explicitly marks it as such."""
    inline = _percent(cells[index])
    if inline is not None and 0 <= inline <= 100:
        return inline
    if index + 1 < len(cells):
        marker = _clean(cells[index + 1]).lower().rstrip(".")
        if marker in _PERCENT_MARKERS:
            value = _numeric(cells[index])
            if value is not None and 0 <= float(value) <= 100:
                return float(value)
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
    # Voting power is a different metric from beneficial ownership percentage.
    # Never flatten either a raw vote count or a voting-power percentage into the
    # generic ownership fields exposed by the Research Monitor.
    if "voting power" in h:
        return None
    if re.search(r"before|prior to|pre-offering|pre offering", h):
        return "percent_before" if is_pct else "shares_before"
    if re.search(r"after|following|post-offering|post offering", h):
        return "percent_after" if is_pct else "shares_after"
    if is_pct and re.search(r"beneficial|owned|class", h):
        return "percent"
    if re.search(r"number|shares", h) and re.search(r"beneficial|owned", h):
        return "shares"
    return None


def _share_class(header):
    """Return an explicit common-stock class identifier from a composite header."""
    normalized = str(header or "").lower()
    if "convertible common stock" in normalized:
        return "convertible"
    match = _SHARE_CLASS_RE.search(normalized)
    return match.group(1).lower() if match else None


def _safe_paired_multiclass_kinds(headers):
    """Return temporal share fields that can be safely aggregated across classes.

    A point-in-time class-agnostic total is defensible when that temporal group
    explicitly reports two or more share classes. The before and after groups do
    not have to expose the same classes: a reorganization can legitimately change
    the security structure at the IPO. A one-class-before/one-class-after table is
    still unsafe and remains unaggregated.
    """
    classes_by_kind = {"shares_before": set(), "shares_after": set()}
    for header in headers:
        kind = _kind(header)
        share_class = _share_class(header)
        if kind in classes_by_kind and share_class:
            classes_by_kind[kind].add(share_class)
    return {
        kind for kind, classes in classes_by_kind.items()
        if len(classes) >= 2
    }


def _unsafe_unqualified_temporal_kinds(headers, safe_multiclass_kinds):
    """Flag unqualified temporal share totals that cross an explicit class change.

    Some IPO reorganizations report predecessor ordinary shares before the
    offering but multiple classes of registrant common stock after it. Because the
    public schema has no security-class/basis dimension, carrying that predecessor
    count into generic ``shares_before`` creates a false apples-to-apples ownership
    transition. Percentages remain usable, and an independently complete
    multi-class after group can still be aggregated safely.
    """
    classes_by_kind = {"shares_before": set(), "shares_after": set()}
    has_unqualified = {"shares_before": False, "shares_after": False}
    for header in headers:
        kind = _kind(header)
        if kind not in classes_by_kind:
            continue
        share_class = _share_class(header)
        if share_class:
            classes_by_kind[kind].add(share_class)
        else:
            has_unqualified[kind] = True

    unsafe = set()
    pairs = (("shares_before", "shares_after"), ("shares_after", "shares_before"))
    for kind, other_kind in pairs:
        if (
            has_unqualified[kind]
            and kind not in safe_multiclass_kinds
            and len(classes_by_kind[other_kind]) >= 2
        ):
            unsafe.add(kind)
    return unsafe


def _aggregate_class_counts(row, headers, base_kinds, aggregate_kind):
    """Sum an explicitly complete multi-class temporal share group, else return None."""
    expected_classes = {
        _share_class(header)
        for header, kind in zip(headers, base_kinds)
        if kind == aggregate_kind and _share_class(header)
    }
    values_by_class = {}
    for i, (header, kind) in enumerate(zip(headers, base_kinds)):
        share_class = _share_class(header)
        if kind != aggregate_kind or not share_class:
            continue
        cell = row[i] if i < len(row) else ""
        cleaned = _clean(cell)
        # SEC tables often place an empty presentation cell between a numeric
        # value and its percentage marker. Composite colspan headers repeat the
        # class label over that spacer, so it must not make the class incomplete.
        if not cleaned:
            continue
        # Never aggregate a percentage-marked cell into a share count even if SEC
        # colspan markup causes the composite header to look like a share column.
        if _explicit_percent(row, i) is not None:
            continue
        number = _numeric(cell)
        if number is None:
            # An explicit dash in an SEC ownership table denotes no shares in
            # that class. Blank or otherwise unparseable content remains unknown.
            if cleaned in {"—", "-"}:
                number = 0
            else:
                return None
        values_by_class.setdefault(share_class, set()).add(number)
    if set(values_by_class) != expected_classes:
        return None
    # Multiple distinct numbers for one class are ambiguous and must not be
    # flattened into a generic class-agnostic total.
    if any(len(values) != 1 for values in values_by_class.values()):
        return None
    total = sum(next(iter(values)) for values in values_by_class.values())
    return total if total > 0 else None


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
            return _clean_holder_label(text)
        if _numeric(text) is not None or _percent(text) is not None:
            break
    return None


def parse_ownership_table(table):
    """Return rich holder dictionaries from one ownership table."""
    if not _looks_like_ownership(table):
        return []
    matrix = _matrix(table)
    headers, start = _composite_headers(matrix)
    base_kinds = [_kind(header) for header in headers]
    share_classes = {share_class for header in headers if (share_class := _share_class(header))}
    multi_class = len(share_classes) > 1
    safe_multiclass_kinds = _safe_paired_multiclass_kinds(headers) if multi_class else set()
    unsafe_unqualified_temporal_kinds = (
        _unsafe_unqualified_temporal_kinds(headers, safe_multiclass_kinds)
        if multi_class else set()
    )
    # The public ownership schema currently has no share-class dimension. Never
    # flatten an explicitly class-specific count or percentage directly into a
    # generic ownership field. Explicitly complete multi-class temporal share
    # groups are aggregated below; isolated one-class continuation tables stay
    # blank unless another table supplies class-agnostic support. An unqualified
    # predecessor count is also suppressed when the opposite temporal group is
    # explicitly multi-class, because those security bases are not safely
    # comparable in the generic public schema.
    kinds = [
        None if (
            _share_class(header)
            or (
                multi_class
                and base_kinds[i] in unsafe_unqualified_temporal_kinds
            )
        ) else base_kinds[i]
        for i, header in enumerate(headers)
    ]
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
            explicit_percent = _explicit_percent(row, i)
            if kind.startswith("percent"):
                value = explicit_percent
                if value is None and "%" in headers[i]:
                    n = _numeric(cell)
                    value = float(n) if n is not None else None
            elif explicit_percent is not None:
                percent_kind = _SHARE_TO_PERCENT.get(kind)
                if percent_kind and data.get(percent_kind) is None:
                    data[percent_kind] = explicit_percent
                continue
            else:
                value = _numeric(cell)
            if value is not None and data.get(kind) is None:
                data[kind] = value

        for aggregate_kind in safe_multiclass_kinds:
            total = _aggregate_class_counts(row, headers, base_kinds, aggregate_kind)
            if total is not None:
                data[aggregate_kind] = total

        # A lone numeric cell is only a safe share-count fallback when the row did
        # not already yield a percentage and the table has no explicit share-class
        # dimension. SEC ownership tables commonly split a percentage value and
        # its "%" marker across cells/continuation tables; reusing that disclosed
        # percentage or an isolated class-specific count as shares fabricates a
        # class-agnostic holding value.
        if (
            not share_classes
            and all(data[k] is None for k in ("shares_before", "shares_sold", "shares_after", "shares"))
            and all(data[k] is None for k in ("percent_before", "percent_after", "percent"))
        ):
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
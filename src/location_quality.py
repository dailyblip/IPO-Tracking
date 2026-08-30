"""Repair malformed or stale public issuer locations without guessing.

SEC prospectus HTML is flattened before address extraction, which can occasionally
leave an address fragment in the city field (for example, ``Eagle Parkway Fort
Worth, TX``). Prefer the filing's principal-executive-office disclosure whenever it
can be recovered reliably. Use SEC submissions metadata only as a fallback, and
cross-check metadata-derived locations against the filing when possible.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import edgar_client


_LOCATION_RE = re.compile(r"^([^,]+),\s*([A-Za-z]{2})$")
_UNIT_MARKER_RE = re.compile(
    r"\b(?:floor|suite|ste|unit|building|bldg|room|level)\b", re.IGNORECASE
)
_SEC_HEADER_RE = re.compile(r"\bsecurities\s+and\s+exchange\s+commission\b", re.IGNORECASE)
# A street-type token followed by another word is strong evidence that flattened
# address text leaked into the city field (e.g. ``Technology Court Broomfield``).
# Requiring a following token avoids rejecting legitimate place names such as
# ``Street, MD`` merely because the city itself matches a street-type word.
_ADDRESS_CONTAMINATION_RE = re.compile(
    r"\b(?:avenue|boulevard|court|drive|highway|parkway|road|street)\b\s+\S+",
    re.IGNORECASE,
)
# A flattened cover can also leave only a street-suffix abbreviation before the
# real city, e.g. ``5801 S. 2nd St. Vernon, CA`` becoming ``St. Vernon, CA``.
# Some legitimate cities also begin with ``St.``, so this is not an automatic
# rejection. It is a signal to cross-check official SEC submissions metadata.
_STREET_SUFFIX_PREFIX_RE = re.compile(
    r"^(?:st|street|ave|avenue|blvd|boulevard|dr|drive|rd|road|ct|court|"
    r"hwy|highway|pkwy|parkway)\.?\s+\S+",
    re.IGNORECASE,
)
_STREET_SUFFIX = (
    r"(?:avenue|ave\.?|boulevard|blvd\.?|court|ct\.?|drive|dr\.?|"
    r"highway|hwy\.?|lane|ln\.?|parkway|pkwy\.?|road|rd\.?|street|st\.?)"
)
_FLATTENED_ADDRESS_CITY_RE = re.compile(
    rf"^.*?\b{_STREET_SUFFIX}"
    r"(?:,\s*(?:suite|ste\.?|unit|floor|fl\.?)\s*[A-Za-z0-9-]+)?\s+"
    r"([A-Za-z][A-Za-z .'-]{1,60}),\s*([A-Za-z]{2})$",
    re.IGNORECASE,
)
_FILING_ADDRESS_CITY_RE = re.compile(
    rf"\b\d{{1,6}}\s+[A-Za-z0-9 .#'&/-]{{1,100}}?\b{_STREET_SUFFIX}"
    r"(?:,\s*(?:suite|ste\.?|unit|floor|fl\.?)\s*[A-Za-z0-9-]+)?\s+"
    r"([A-Za-z][A-Za-z .'-]{1,60}),\s*([A-Z]{2})\s+\d{5}(?:-\d{4})?",
    re.IGNORECASE,
)


def normalize_location(value):
    """Return a defensible compact ``City, ST`` value or ``None``.

    The validator is intentionally conservative. It does not try to reconstruct a
    city from contaminated address text because a plausible guess is worse than a
    blank research field.
    """
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return None
    match = _LOCATION_RE.fullmatch(text)
    if not match:
        return None

    city = match.group(1).strip(" ,")
    state = match.group(2).upper()
    if not city or any(character.isdigit() for character in city):
        return None
    if _UNIT_MARKER_RE.search(city):
        return None
    if _SEC_HEADER_RE.search(city):
        return None
    if _ADDRESS_CONTAMINATION_RE.search(city):
        return None
    return f"{city}, {state}"


def _recover_trailing_city_from_flattened_address(value):
    """Recover only an explicit trailing city/state from address-contaminated text."""
    text = " ".join(str(value or "").split()).strip()
    match = _FLATTENED_ADDRESS_CITY_RE.fullmatch(text)
    if not match:
        return None
    return normalize_location(f"{match.group(1).strip()}, {match.group(2).upper()}")


def _needs_authoritative_cross_check(location):
    """Return True for compact locations that may begin with a street suffix.

    Values such as ``St. Louis, MO`` are legitimate, so callers must never treat
    this signal as proof of contamination. A differing authoritative SEC location
    is required before replacement.
    """
    normalized = normalize_location(location)
    if not normalized:
        return False
    city = normalized.rsplit(",", 1)[0].strip()
    return bool(_STREET_SUFFIX_PREFIX_RE.search(city))


def _resolve_authoritative_location(filing, resolve_location):
    """Resolve a normalized SEC submissions location without inferring values."""
    cik = str(filing.get("cik") or "").strip()
    if not cik:
        return None
    try:
        return normalize_location(resolve_location(cik))
    except Exception as exc:  # release sanitation must not preserve known-bad data
        print(
            f"Location quality gate: SEC fallback failed for "
            f"{filing.get('company') or filing.get('id')}: {exc}"
        )
        return None


def _extract_filing_principal_office_location(soup):
    """Extract a filing-disclosed principal office from a tightly anchored address."""
    cover_text = soup.get_text(" ", strip=True)[:100000]
    label = re.search(r"\(Address[^)]*principal executive offices\)", cover_text, re.I)
    search_text = (
        cover_text[max(0, label.start() - 800) : label.start()]
        if label
        else cover_text
    )
    matches = list(_FILING_ADDRESS_CITY_RE.finditer(search_text))
    if not matches:
        return None
    match = matches[-1]
    return normalize_location(f"{match.group(1).strip()}, {match.group(2).upper()}")


def _resolve_filing_location(filing):
    """Resolve the principal office from the row's own SEC filing when available."""
    sec_url = str(filing.get("sec_url") or "").strip()
    if not sec_url:
        return None
    try:
        import filing_parser

        form = str(filing.get("form") or "").strip().upper()
        expected_forms = [form] if form in {"S-1", "S-1/A", "424B4"} else None
        if "-index" in sec_url.lower():
            document_url = filing_parser.find_primary_document_url(
                sec_url, expected_form_types=expected_forms
            )
        else:
            document_url = sec_url
        soup = filing_parser.fetch_document(document_url)
        direct = _extract_filing_principal_office_location(soup)
        if direct:
            return direct
        return normalize_location(filing_parser.extract_principal_office_location(soup))
    except Exception as exc:
        print(
            f"Location quality gate: filing-office lookup failed for "
            f"{filing.get('company') or filing.get('id')}: {exc}"
        )
        return None


def _filing_location_source(filing):
    form = str(filing.get("form") or "").strip().upper()
    if form in {"S-1", "S-1/A", "424B4"}:
        return f"{form} principal executive office"
    return "SEC filing principal executive office"


def repair_payload(
    payload,
    resolve_location=edgar_client.get_business_location,
    resolve_filing_location=_resolve_filing_location,
):
    """Repair/clear malformed or stale locations in a public-feed payload.

    ``resolve_location`` and ``resolve_filing_location`` are injectable for tests.
    Filing-disclosed principal-office evidence outranks submissions metadata. A
    malformed flattened address is repaired only when its trailing city/state is
    explicit; otherwise official SEC metadata is used as fallback. Provider/network
    errors never cause a guessed replacement.
    """
    filings = payload.get("filings", []) if isinstance(payload, dict) else []
    changes = []
    filing_location_cache = {}

    def filing_location_for(filing):
        key = str(filing.get("sec_url") or filing.get("id") or "").strip()
        if not key:
            return None
        if key not in filing_location_cache:
            try:
                filing_location_cache[key] = normalize_location(
                    resolve_filing_location(filing)
                )
            except Exception as exc:
                print(
                    f"Location quality gate: filing-office resolver failed for "
                    f"{filing.get('company') or filing.get('id')}: {exc}"
                )
                filing_location_cache[key] = None
        return filing_location_cache[key]

    for filing in filings:
        if not isinstance(filing, dict):
            continue
        raw_location = filing.get("location")
        if raw_location in (None, ""):
            continue

        company = filing.get("company") or filing.get("id") or "Unknown issuer"
        normalized = normalize_location(raw_location)
        if normalized:
            source = str(filing.get("location_source") or "").strip().casefold()
            if source == "sec submissions metadata":
                filing_location = filing_location_for(filing)
                if filing_location and filing_location != normalized:
                    filing["location"] = filing_location
                    filing["location_source"] = _filing_location_source(filing)
                    changes.append((company, raw_location, filing_location))
                    continue

            if _needs_authoritative_cross_check(normalized):
                replacement = _resolve_authoritative_location(filing, resolve_location)
                if replacement and replacement != normalized:
                    filing["location"] = replacement
                    filing["location_source"] = "SEC submissions metadata"
                    changes.append((company, raw_location, replacement))
                    continue
            if normalized != raw_location:
                filing["location"] = normalized
                changes.append((company, raw_location, normalized))
            continue

        recovered = _recover_trailing_city_from_flattened_address(raw_location)
        if recovered:
            filing["location"] = recovered
            if not str(filing.get("location_source") or "").strip():
                filing["location_source"] = _filing_location_source(filing)
            changes.append((company, raw_location, recovered))
            continue

        replacement = _resolve_authoritative_location(filing, resolve_location)
        if replacement:
            filing_location = filing_location_for(filing)
            if filing_location:
                replacement = filing_location
                filing["location_source"] = _filing_location_source(filing)
            else:
                filing["location_source"] = "SEC submissions metadata"
            filing["location"] = replacement
            changes.append((company, raw_location, replacement))
        else:
            filing.pop("location", None)
            filing.pop("location_source", None)
            changes.append((company, raw_location, None))

    return payload, changes


def repair_feed(path):
    """Apply the release gate to JSON and keep the CSV export synchronized."""
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload, changes = repair_payload(payload)
    if not changes:
        print("Location quality gate: no malformed published locations found")
        return 0

    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)

    try:
        from dashboard_export import write_dashboard_csv

        write_dashboard_csv(payload.get("filings", []), path)
    except ImportError:
        pass

    for company, old, new in changes:
        if new:
            print(f"Location quality gate: {company}: {old!r} -> {new!r}")
        else:
            print(f"Location quality gate: {company}: cleared malformed {old!r}")
    print(f"Location quality gate: repaired/cleared {len(changes)} location(s)")
    return len(changes)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Repair malformed public issuer locations using official SEC evidence."
    )
    parser.add_argument("feed", help="Path to docs/data/filings.json")
    args = parser.parse_args(argv)
    try:
        repair_feed(args.feed)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()

"""Repair malformed public issuer locations without guessing.

SEC prospectus HTML is flattened before address extraction, which can occasionally
leave an address-unit fragment in the city field (for example, ``th Floor Cambridge,
MA``). The public Research Monitor should never publish a location that is visibly
malformed. This release gate keeps clean ``City, ST`` values, replaces malformed
values only with official SEC submissions metadata, and otherwise clears them.
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
    r"\b(?:avenue|boulevard|court|drive|highway|parkway|street)\b\s+\S+",
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


def repair_payload(payload, resolve_location=edgar_client.get_business_location):
    """Repair/clear malformed locations in a public-feed payload.

    ``resolve_location`` is injectable for tests. Provider/network errors are treated
    as unresolved data: visibly malformed values are cleared rather than retained or
    replaced with an inference. Ambiguous street-suffix-prefixed values are replaced
    only when official SEC metadata supplies a different, valid location.
    """
    filings = payload.get("filings", []) if isinstance(payload, dict) else []
    changes = []

    for filing in filings:
        if not isinstance(filing, dict):
            continue
        raw_location = filing.get("location")
        if raw_location in (None, ""):
            continue

        normalized = normalize_location(raw_location)
        if normalized:
            if _needs_authoritative_cross_check(normalized):
                replacement = _resolve_authoritative_location(filing, resolve_location)
                if replacement and replacement != normalized:
                    company = filing.get("company") or filing.get("id") or "Unknown issuer"
                    filing["location"] = replacement
                    filing["location_source"] = "SEC submissions metadata"
                    changes.append((company, raw_location, replacement))
                    continue
            if normalized != raw_location:
                filing["location"] = normalized
                changes.append(
                    (filing.get("company") or filing.get("id") or "Unknown issuer", raw_location, normalized)
                )
            continue

        replacement = _resolve_authoritative_location(filing, resolve_location)
        company = filing.get("company") or filing.get("id") or "Unknown issuer"
        if replacement:
            filing["location"] = replacement
            filing["location_source"] = "SEC submissions metadata"
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
        description="Repair malformed public issuer locations using official SEC metadata."
    )
    parser.add_argument("feed", help="Path to docs/data/filings.json")
    args = parser.parse_args(argv)
    try:
        repair_feed(args.feed)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()

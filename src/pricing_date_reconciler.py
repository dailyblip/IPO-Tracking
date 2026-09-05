"""Repair priced IPO dates from the authoritative final 424B4 prospectus.

The SEC filing date is not necessarily the IPO pricing date. Final prospectuses
are commonly filed the morning after a deal prices, so treating the 424B4 filing
date as Pricing Date can shift the event by a day. This reconciler only replaces
a stored date when the final 424B4 itself identifies its prospectus date. It never
infers a pricing date from trading dates or filing chronology.

Lock-up end dates are derived from the same pricing/prospectus date plus explicit
SEC-disclosed durations. When Pricing Date is repaired, those derived dates must
move with it instead of retaining stale filing-date arithmetic.
"""

from __future__ import annotations

import argparse
import calendar
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import edgar_client
import filing_parser
from dashboard_export import write_dashboard_csv

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"

_DATE_TEXT = r"([A-Z][a-z]{2,8}\.?\s+\d{1,2},\s+\d{4})"
_EXPLICIT_PROSPECTUS_DATE_PATTERNS = (
    re.compile(rf"\bthe\s+date\s+of\s+this\s+prospectus\s+is\s+{_DATE_TEXT}", re.I),
    re.compile(rf"\b(?:final\s+)?prospectus\s+dated(?:\s+as\s+of)?\s+{_DATE_TEXT}", re.I),
)
_STANDALONE_DATE_PATTERN = re.compile(rf"^{_DATE_TEXT}$", re.I)


def _iso_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def _parse_month_date(value):
    cleaned = " ".join(str(value or "").replace("\xa0", " ").split())
    cleaned = re.sub(r"\bSept\.", "Sep", cleaned, flags=re.I)
    cleaned = re.sub(r"\b([A-Z][a-z]{2})\.", r"\1", cleaned)
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass
    return None


def _candidate_is_plausible(candidate, filed):
    if candidate is None:
        return False
    if filed is None:
        return True
    delta = (filed - candidate).days
    return 0 <= delta <= 10


def _extract_back_cover_date(raw_text, filed):
    """Recover a final-prospectus date from a labeled back cover.

    Some SEC HTML filings omit the words "Prospectus dated" around the final
    date while preserving a back-cover PROSPECTUS label followed by a standalone
    date. Limit this fallback to the document tail and a narrow line window after
    the final PROSPECTUS marker so unrelated dates elsewhere are not promoted.
    """
    tail = str(raw_text or "")[-12000:]
    lines = [" ".join(line.replace("\xa0", " ").split()) for line in tail.splitlines()]
    lines = [line for line in lines if line]
    marker_indexes = [
        index for index, line in enumerate(lines) if line.strip().upper() == "PROSPECTUS"
    ]
    if not marker_indexes:
        return None

    marker_index = marker_indexes[-1]
    following = lines[marker_index + 1 : marker_index + 81]
    for line in reversed(following):
        match = _STANDALONE_DATE_PATTERN.fullmatch(line)
        if not match:
            continue
        candidate = _parse_month_date(match.group(1))
        if _candidate_is_plausible(candidate, filed):
            return candidate.isoformat()
    return None


def _extract_front_cover_date(raw_text, filed):
    """Recover an unlabeled final-prospectus date from a structured IPO cover.

    Some final 424B4 covers disclose the prospectus date as a standalone line
    beneath the underwriters rather than as "Prospectus dated ...". Accept that
    layout only when it follows both the initial-public-offering price language
    and the expected-delivery sentence, and only before the first subsequent
    table-of-contents marker. Multiple plausible dates fail closed.
    """
    lines = [
        " ".join(line.replace("\xa0", " ").split())
        for line in str(raw_text or "").splitlines()
    ]
    lines = [line for line in lines if line]
    cover = lines[:260]

    offering_index = next(
        (
            index
            for index, line in enumerate(cover)
            if "initial public offering price" in line.casefold()
        ),
        None,
    )
    if offering_index is None:
        return None

    delivery_index = next(
        (
            index
            for index, line in enumerate(cover[offering_index + 1 :], offering_index + 1)
            if "expect to deliver" in line.casefold()
            or "delivery of the shares" in line.casefold()
            or "delivery of shares" in line.casefold()
        ),
        None,
    )
    if delivery_index is None:
        return None

    candidates = []
    for line in cover[delivery_index + 1 : delivery_index + 81]:
        if line.strip().upper() == "TABLE OF CONTENTS":
            break
        match = _STANDALONE_DATE_PATTERN.fullmatch(line)
        if not match:
            continue
        candidate = _parse_month_date(match.group(1))
        if not _candidate_is_plausible(candidate, filed):
            continue
        iso = candidate.isoformat()
        if iso not in candidates:
            candidates.append(iso)

    return candidates[0] if len(candidates) == 1 else None


def extract_authoritative_pricing_date(soup, sec_filing_date=None):
    """Return an ISO prospectus date only from explicit final-prospectus language.

    A candidate must not post-date the SEC filing and must be close to that filing.
    The narrow ten-day window rejects historical prospectus references elsewhere in
    long registration documents while accommodating weekends and filing delays.
    """
    raw_text = soup.get_text("\n", strip=True).replace("\xa0", " ")
    text = " ".join(raw_text[:120000].split())
    filed = _iso_date(sec_filing_date)

    for pattern in _EXPLICIT_PROSPECTUS_DATE_PATTERNS:
        for match in pattern.finditer(text):
            candidate = _parse_month_date(match.group(1))
            if _candidate_is_plausible(candidate, filed):
                return candidate.isoformat()

    front_cover = _extract_front_cover_date(raw_text, filed)
    if front_cover:
        return front_cover
    return _extract_back_cover_date(raw_text, filed)


def _add_duration(start_date, value, unit):
    """Apply only an explicit lock-up duration to an authoritative pricing date."""
    base = _iso_date(start_date)
    if base is None or value in (None, "") or not str(unit or "").strip():
        return None
    try:
        duration = int(value)
    except (TypeError, ValueError):
        return None
    if duration <= 0:
        return None

    normalized_unit = str(unit).strip().casefold()
    if normalized_unit == "days":
        return (base + timedelta(days=duration)).isoformat()
    if normalized_unit == "months":
        month_index = base.month - 1 + duration
        year = base.year + month_index // 12
        month = month_index % 12 + 1
        day = min(base.day, calendar.monthrange(year, month)[1])
        return base.replace(year=year, month=month, day=day).isoformat()
    if normalized_unit == "years":
        try:
            return base.replace(year=base.year + duration).isoformat()
        except ValueError:
            return base.replace(month=2, day=28, year=base.year + duration).isoformat()
    return None


def _retime_term(term, pricing_date):
    if not isinstance(term, dict):
        return False
    end_date = _add_duration(
        pricing_date,
        term.get("duration_value"),
        term.get("duration_unit"),
    )
    if not end_date or term.get("end_date") == end_date:
        return False
    term["end_date"] = end_date
    return True


def _reconcile_lockup_dates(filing, pricing_date):
    """Keep derived filing/person lock-up dates aligned with authoritative Pricing Date."""
    touched = False

    filing_end = _add_duration(
        pricing_date,
        filing.get("lockup_duration_value"),
        filing.get("lockup_duration_unit"),
    )
    if filing_end and filing.get("lockup_end_date") != filing_end:
        filing["lockup_end_date"] = filing_end
        touched = True

    terms = filing.get("lockup_terms")
    if isinstance(terms, list):
        for term in terms:
            touched = _retime_term(term, pricing_date) or touched

    people = filing.get("people")
    if not isinstance(people, list):
        return touched

    for person in people:
        if not isinstance(person, dict):
            continue

        person_end = _add_duration(
            pricing_date,
            person.get("lockup_duration_value"),
            person.get("lockup_duration_unit"),
        )
        if person_end and person.get("lockup_end_date") != person_end:
            person["lockup_end_date"] = person_end
            touched = True

        schedule = person.get("lockup_schedule")
        if isinstance(schedule, list):
            for term in schedule:
                touched = _retime_term(term, pricing_date) or touched

    return touched


def _load_final_soup(filing):
    cik = str(filing.get("cik") or "").strip()
    accession = str(filing.get("accession_no") or "").strip()
    sec_url = str(filing.get("sec_url") or "").strip()
    if not sec_url:
        if not cik or not accession:
            raise ValueError("Priced 424B4 record lacks SEC identity provenance")
        sec_url = edgar_client.build_filing_index_url(cik, accession)
    document_url = filing_parser.find_primary_document_url(
        sec_url, expected_form_types=["424B4"]
    )
    return filing_parser.fetch_document(document_url)


def reconcile_payload(payload, soup_loader=_load_final_soup):
    """Repair authoritative Pricing Date and any lock-up dates derived from it."""
    filings = payload.get("filings", []) if isinstance(payload, dict) else []
    changed = 0
    checked = 0
    failures = []

    for filing in filings:
        if not isinstance(filing, dict):
            continue
        if str(filing.get("form") or "").strip().upper() != "424B4":
            continue
        if str(filing.get("stage") or "").strip().casefold() != "priced":
            continue
        if not filing.get("offering_price"):
            continue

        checked += 1
        try:
            soup = soup_loader(filing)
        except Exception as error:
            failures.append(
                f"{filing.get('company') or filing.get('id') or '<unknown>'}: {error}"
            )
            continue

        authoritative = extract_authoritative_pricing_date(soup, filing.get("filed"))
        if not authoritative:
            # main.py historically seeded the SEC 424B4 filing date into Pricing Date.
            # When the final prospectus can be read but supplies no authoritative date,
            # an identical stored value is therefore an unverified filing-date fallback,
            # not pricing evidence. Clear it so the downstream release gate fails closed
            # rather than publishing an inferred Pricing Date.
            stored = str(filing.get("pricing_date") or "").strip()
            filed = str(filing.get("filed") or "").strip()
            if stored and filed and stored == filed:
                filing["pricing_date"] = None
                changed += 1
            continue

        row_changed = False
        if authoritative != str(filing.get("pricing_date") or "").strip():
            filing["pricing_date"] = authoritative
            row_changed = True

        # Existing rows may already have the corrected Pricing Date while retaining
        # lock-up dates calculated earlier from the SEC filing date. Reconcile these
        # on every authoritative review, not only on the first date correction.
        row_changed = _reconcile_lockup_dates(filing, authoritative) or row_changed
        if row_changed:
            changed += 1

    if changed:
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    return payload, changed, checked, failures


def reconcile_file(path: Path = DEFAULT_PATH) -> tuple[int, int, list[str]]:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload, changed, checked, failures = reconcile_payload(payload)
    if changed:
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temp.replace(path)
        write_dashboard_csv(payload.get("filings", []), path)
    return changed, checked, failures


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile IPO Pricing Date and pricing-date-derived lock-up dates "
            "from explicit final 424B4 prospectus dates"
        )
    )
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    changed, checked, failures = reconcile_file(args.path)
    print(
        f"Checked {checked} priced 424B4 filing(s); repaired {changed} "
        "authoritative Pricing Date/lock-up record(s)."
    )
    for failure in failures:
        print(f"[pricing_date_reconciler] SEC lookup unavailable: {failure}")


if __name__ == "__main__":
    main()

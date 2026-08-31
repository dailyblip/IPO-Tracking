"""Repair priced IPO dates from the authoritative final 424B4 prospectus.

The SEC filing date is not necessarily the IPO pricing date. Final prospectuses
are commonly filed the morning after a deal prices, so treating the 424B4 filing
date as Pricing Date can shift the event by a day. This reconciler only replaces
a stored date when the final 424B4 itself explicitly identifies its prospectus
date. It never infers a pricing date from trading dates or filing chronology.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
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


def extract_authoritative_pricing_date(soup, sec_filing_date=None):
    """Return an ISO prospectus date only from explicit final-prospectus language.

    A candidate must not post-date the SEC filing and must be close to that filing.
    The narrow ten-day window rejects historical prospectus references elsewhere in
    long registration documents while accommodating weekends and filing delays.
    """
    text = " ".join(soup.get_text(" ", strip=True)[:120000].replace("\xa0", " ").split())
    filed = _iso_date(sec_filing_date)

    for pattern in _EXPLICIT_PROSPECTUS_DATE_PATTERNS:
        for match in pattern.finditer(text):
            candidate = _parse_month_date(match.group(1))
            if candidate is None:
                continue
            if filed is not None:
                delta = (filed - candidate).days
                if delta < 0 or delta > 10:
                    continue
            return candidate.isoformat()
    return None


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
    """Replace stale/fallback Pricing Dates when the final prospectus proves a date."""
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
        if authoritative and authoritative != str(filing.get("pricing_date") or "").strip():
            filing["pricing_date"] = authoritative
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
        description="Reconcile IPO Pricing Date from explicit final 424B4 prospectus dates"
    )
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    changed, checked, failures = reconcile_file(args.path)
    print(
        f"Checked {checked} priced 424B4 filing(s); repaired {changed} authoritative Pricing Date(s)."
    )
    for failure in failures:
        print(f"[pricing_date_reconciler] SEC lookup unavailable: {failure}")


if __name__ == "__main__":
    main()

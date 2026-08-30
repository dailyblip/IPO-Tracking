"""Preserve authoritative final 424B4 aggregate IPO values and share terms.

The core parser derives gross offering value from base IPO shares × final price.
Final prospectuses sometimes publish a rounded authoritative aggregate that can
differ by cents from that arithmetic. This release-stage reconciler preserves
the SEC table value when it agrees within a strict rounding tolerance and fails
closed on larger conflicts so bad economics cannot be silently published.

It also repairs a narrower completeness case: when the final prospectus explicitly
states that the issuer itself is offering a specific number of shares but the
published primary-offering share field is blank, preserve that SEC-disclosed count.
No secondary count is inferred from arithmetic or from a missing disclosure.
"""

import csv
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import filing_parser

ROUNDING_TOLERANCE_DOLLARS = 1.0
RECENT_PRICING_DAYS = 45
SOURCE_MARKER = "authoritative final 424B4 aggregate IPO price table"
PRIMARY_SHARES_MARKER = "explicit issuer offering statement in final 424B4"


class OfferingValueReconciliationError(RuntimeError):
    pass


def _number(value):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def extract_authoritative_aggregate(text, expected_price=None):
    """Return the explicit final IPO aggregate from a prospectus cover table.

    Requires the IPO/public-offering price row to contain both a per-share dollar
    amount and a total dollar amount. If ``expected_price`` is supplied, the row's
    per-share value must match it within one cent.
    """
    normalized = " ".join(str(text or "").split())
    patterns = [
        r"initial public offering price.{0,80}?\$\s*(\d{1,4}(?:\.\d{1,5})?).{0,80}?\$\s*([\d,]{4,}(?:\.\d{1,2})?)",
        r"public offering price.{0,80}?\$\s*(\d{1,4}(?:\.\d{1,5})?).{0,80}?\$\s*([\d,]{4,}(?:\.\d{1,2})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, re.I)
        if not match:
            continue
        per_share = _number(match.group(1))
        aggregate = _number(match.group(2))
        if per_share is None or aggregate is None or aggregate <= 0:
            continue
        if expected_price is not None:
            expected = _number(expected_price)
            if expected is None or abs(per_share - expected) > 0.01:
                continue
        return aggregate
    return None


def extract_authoritative_primary_shares(text):
    """Return an explicitly disclosed issuer-primary share count from the cover.

    This is intentionally narrower than a generic ``N shares`` extractor. The
    sentence must identify the issuer (or ``we``) as the party offering shares of
    its/our common stock and appear next to explicit initial-public-offering
    language. Selling-stockholder subjects are rejected. This captures final covers
    such as Scribe Therapeutics' ``Scribe Therapeutics Inc. is offering 8,580,000
    shares of its common stock`` without deriving a share count from offering value.
    """
    normalized = " ".join(str(text or "").split())[:30000]
    pattern = re.compile(
        r"(?P<subject>\b(?:we|[A-Z][A-Za-z0-9&.,'’()/-]*(?:\s+[A-Za-z0-9&.,'’()/-]+){0,12}))"
        r"\s+(?:is|are)\s+offering\s+(?P<shares>[\d,]{4,})\s+shares\s+of\s+"
        r"(?:its|our)\s+(?:(?:class|series)\s+[A-Z0-9-]+\s+)?common\s+stock\b",
        re.I,
    )
    for match in pattern.finditer(normalized):
        subject = match.group("subject").casefold()
        if "selling stockholder" in subject or "selling shareholder" in subject:
            continue
        context = normalized[
            max(0, match.start() - 250): min(len(normalized), match.end() + 400)
        ].casefold()
        if "initial public offering" not in context:
            continue
        shares = _number(match.group("shares"))
        if shares is not None and shares.is_integer() and shares > 0:
            return int(shares)
    return None


def _recent_priced(filing, today=None):
    today = today or date.today()
    raw = filing.get("pricing_date") or filing.get("filed")
    try:
        priced = datetime.strptime(str(raw), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return False
    return priced >= today - timedelta(days=RECENT_PRICING_DAYS)


def _needs_check(filing, today=None):
    if str(filing.get("form") or "").upper() != "424B4":
        return False
    if str(filing.get("stage") or "").casefold() != "priced":
        return False
    value = _number(filing.get("value"))
    has_fractional_value = value is not None and abs(value - round(value)) > 1e-9
    return has_fractional_value or _recent_priced(filing, today=today)


def _append_source_marker(filing, marker):
    source = str(filing.get("offering_size_source") or "").strip()
    if marker.casefold() not in source.casefold():
        filing["offering_size_source"] = f"{source}; {marker}" if source else marker
        return True
    return False


def reconcile_record(filing, aggregate, primary_shares=None):
    """Reconcile SEC cover economics and explicit issuer-primary share disclosure."""
    changed = False
    current = _number(filing.get("value"))
    aggregate = _number(aggregate)
    if aggregate is not None:
        if current is None:
            raise OfferingValueReconciliationError(
                f"{filing.get('company')}: SEC aggregate {aggregate:,.2f} found but published offering value is blank"
            )
        difference = abs(current - aggregate)
        if difference > ROUNDING_TOLERANCE_DOLLARS:
            raise OfferingValueReconciliationError(
                f"{filing.get('company')}: published offering value {current:,.2f} conflicts with "
                f"authoritative SEC aggregate {aggregate:,.2f} by {difference:,.2f}"
            )
        if difference > 1e-9:
            filing["value"] = int(aggregate) if aggregate.is_integer() else aggregate
            changed = True
        if _append_source_marker(filing, SOURCE_MARKER):
            changed = True

    explicit_primary = _number(primary_shares)
    if explicit_primary is not None:
        if not explicit_primary.is_integer():
            raise OfferingValueReconciliationError(
                f"{filing.get('company')}: SEC issuer-primary share count is not an integer: {primary_shares!r}"
            )
        explicit_primary = int(explicit_primary)
        published_primary = _number(filing.get("primary_offering_shares"))
        if published_primary is not None and int(published_primary) != explicit_primary:
            raise OfferingValueReconciliationError(
                f"{filing.get('company')}: published primary offering shares {int(published_primary):,} "
                f"conflict with explicit SEC issuer offering statement {explicit_primary:,}"
            )
        if published_primary is None:
            filing["primary_offering_shares"] = explicit_primary
            changed = True
        if _append_source_marker(filing, PRIMARY_SHARES_MARKER):
            changed = True

    return changed


def _atomic_json(path, payload):
    path = Path(path)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        tmp = handle.name
    os.replace(tmp, path)


def _sync_csv(csv_path, updates):
    csv_path = Path(csv_path)
    if not csv_path.exists() or not updates:
        return
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        rows = list(reader)
    changed = False
    for row in rows:
        update = updates.get(row.get("accession_no"))
        if not update:
            continue
        row["offering_value"] = str(update["value"])
        row["offering_size_source"] = update["offering_size_source"]
        if update.get("primary_offering_shares") is not None:
            row["primary_offering_shares"] = str(update["primary_offering_shares"])
        changed = True
    if not changed:
        return
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", dir=csv_path.parent, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        tmp = handle.name
    os.replace(tmp, csv_path)


def reconcile_feed(path, today=None):
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    updates = {}
    for filing in payload.get("filings", []):
        if not _needs_check(filing, today=today):
            continue
        sec_url = str(filing.get("sec_url") or "")
        if not sec_url.startswith("https://www.sec.gov/"):
            continue
        try:
            document_url = filing_parser.find_primary_document_url(sec_url, expected_form_types=["424B4"])
            soup = filing_parser.fetch_document(document_url)
            cover_text = soup.get_text(" ", strip=True)[:30000]
            aggregate = extract_authoritative_aggregate(
                cover_text,
                expected_price=filing.get("offering_price"),
            )
            primary_shares = extract_authoritative_primary_shares(cover_text)
        except Exception as error:
            print(f"[offering-value] Warning: could not inspect {filing.get('company')}: {error}")
            continue
        if aggregate is None and primary_shares is None:
            continue
        if reconcile_record(filing, aggregate, primary_shares=primary_shares):
            updates[str(filing.get("accession_no") or "")] = {
                "value": filing.get("value"),
                "primary_offering_shares": filing.get("primary_offering_shares"),
                "offering_size_source": filing.get("offering_size_source") or "",
            }
            if aggregate is not None:
                print(
                    f"[offering-value] {filing.get('company')}: preserved authoritative SEC aggregate "
                    f"${aggregate:,.0f}"
                )
            if primary_shares is not None:
                print(
                    f"[offering-value] {filing.get('company')}: preserved explicit issuer-primary "
                    f"share count {primary_shares:,}"
                )
    if updates:
        _atomic_json(path, payload)
        _sync_csv(path.with_suffix(".csv"), updates)
    return updates


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 1:
        raise SystemExit("Usage: python offering_value_reconciler.py <filings.json>")
    reconcile_feed(argv[0])


if __name__ == "__main__":
    main()

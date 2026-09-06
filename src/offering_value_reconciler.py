"""Preserve authoritative final 424B4 aggregate IPO values and share terms.

The core parser derives gross offering value from base IPO shares × final price.
Final prospectuses sometimes publish an authoritative aggregate that can differ
slightly from that arithmetic because the disclosed total is rounded while the
share count must remain whole. This release-stage reconciler preserves the SEC
table value only when the difference is either within the strict dollar tolerance
or is exactly explainable by the same nearest whole-share count at the final price;
larger conflicts fail closed so bad economics cannot be silently published.

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
IPO_PRICE_TOTAL_PATTERNS = (
    r"initial public offering price.{0,80}?\$\s*(\d{1,4}(?:\.\d{1,5})?).{0,80}?\$\s*([\d,]{4,}(?:\.\d{1,2})?)",
    r"public offering price.{0,80}?\$\s*(\d{1,4}(?:\.\d{1,5})?).{0,80}?\$\s*([\d,]{4,}(?:\.\d{1,2})?)",
)


class OfferingValueReconciliationError(RuntimeError):
    pass


def _number(value):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _format_value_label(value):
    """Return the canonical compact display label for an offering value."""
    value = _number(value)
    if value is None or value <= 0:
        return "—"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def _sync_value_label(filing):
    """Keep derived display metadata consistent with the authoritative raw value."""
    expected = _format_value_label(filing.get("value"))
    if filing.get("value_label") == expected:
        return False
    filing["value_label"] = expected
    return True


def extract_authoritative_final_price(text):
    """Return the final per-share IPO price from an authoritative cover price row.

    The row must contain both the per-share price and aggregate IPO value. Requiring
    both values keeps this narrower than a generic dollar extractor and lets the
    same evidence support the aggregate reconciliation below.
    """
    normalized = " ".join(str(text or "").split())
    for pattern in IPO_PRICE_TOTAL_PATTERNS:
        match = re.search(pattern, normalized, re.I)
        if not match:
            continue
        per_share = _number(match.group(1))
        aggregate = _number(match.group(2))
        if per_share is None or per_share <= 0 or aggregate is None or aggregate <= 0:
            continue
        return per_share
    return None


def validate_authoritative_final_price(filing, authoritative_price):
    """Fail closed when the published final IPO price conflicts with the 424B4.

    This validator intentionally does not invent or repair a missing final price.
    Lifecycle reconciliation remains responsible for population. Here, an explicit
    conflict in a recent priced record is release-blocking because downstream
    offering and person economics can depend on the final price.
    """
    authoritative = _number(authoritative_price)
    published = _number(filing.get("offering_price"))
    if authoritative is None or authoritative <= 0 or published is None or published <= 0:
        return
    if int(round(authoritative * 100)) != int(round(published * 100)):
        raise OfferingValueReconciliationError(
            f"{filing.get('company')}: published final IPO price ${published:,.2f} conflicts with "
            f"authoritative SEC 424B4 final IPO price ${authoritative:,.2f}"
        )


def extract_authoritative_aggregate(text, expected_price=None):
    """Return the explicit final IPO aggregate from a prospectus cover table.

    Requires the IPO/public-offering price row to contain both a per-share dollar
    amount and a total dollar amount. If ``expected_price`` is supplied, the row's
    per-share value must match it within one cent.
    """
    normalized = " ".join(str(text or "").split())
    for pattern in IPO_PRICE_TOTAL_PATTERNS:
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
    if value is None:
        # Existing qualifying IPOs with unknown size remain publishable, but a
        # blank value should still receive an authoritative SEC recovery attempt
        # regardless of age. A failed fetch remains non-destructive below.
        return True
    has_fractional_value = abs(value - round(value)) > 1e-9
    return has_fractional_value or _recent_priced(filing, today=today)


def _append_source_marker(filing, marker):
    source = str(filing.get("offering_size_source") or "").strip()
    if marker.casefold() not in source.casefold():
        filing["offering_size_source"] = f"{source}; {marker}" if source else marker
        return True
    return False


def _same_nearest_whole_share_count(current, aggregate, price):
    """Allow only tiny total-rounding differences that imply the same share count.

    Some final covers publish a rounded aggregate even though the disclosed base
    share count times the exact final price lands a few dollars away. Accept that
    authoritative total only when the current value itself is exact whole-share
    arithmetic and rounding the SEC aggregate back to the nearest whole share at
    the same final price yields that identical count. The half-share bound prevents
    this from masking a one-share (or larger) economics error.
    """
    current = _number(current)
    aggregate = _number(aggregate)
    price = _number(price)
    if current is None or aggregate is None or price is None:
        return False
    if current <= 0 or aggregate <= 0 or price <= 0:
        return False

    current_shares = int((current / price) + 0.5)
    if current_shares <= 0:
        return False
    if abs(current - (current_shares * price)) > 0.01:
        return False

    aggregate_shares = int((aggregate / price) + 0.5)
    if aggregate_shares != current_shares:
        return False

    return abs(current - aggregate) <= (price / 2.0) + 0.01


def reconcile_record(filing, aggregate, primary_shares=None):
    """Reconcile SEC cover economics and explicit issuer-primary share disclosure."""
    changed = False
    current = _number(filing.get("value"))
    aggregate = _number(aggregate)
    if aggregate is not None:
        if current is None:
            filing["value"] = int(aggregate) if aggregate.is_integer() else aggregate
            changed = True
        else:
            difference = abs(current - aggregate)
            if difference > ROUNDING_TOLERANCE_DOLLARS and not _same_nearest_whole_share_count(
                current,
                aggregate,
                filing.get("offering_price"),
            ):
                raise OfferingValueReconciliationError(
                    f"{filing.get('company')}: published offering value {current:,.2f} conflicts with "
                    f"authoritative SEC aggregate {aggregate:,.2f} by {difference:,.2f}"
                )
            if difference > 1e-9:
                filing["value"] = int(aggregate) if aggregate.is_integer() else aggregate
                changed = True
        if _append_source_marker(filing, SOURCE_MARKER):
            changed = True
        # A final 424B4 cover aggregate matched to the row's final IPO price is
        # release-grade SEC evidence. Repair stale/legacy confidence alongside the
        # value and source so authoritative reconciliation cannot leave a populated
        # offering value marked Unresolved.
        if filing.get("offering_size_confidence") != "High":
            filing["offering_size_confidence"] = "High"
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

    if _sync_value_label(filing):
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
        if "offering_size_confidence" in (fieldnames or []):
            row["offering_size_confidence"] = update["offering_size_confidence"]
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
    json_changed = False
    for filing in payload.get("filings", []):
        # value_label is derived presentation metadata, so it can be repaired from
        # an already-populated authoritative value without refetching old filings.
        # This keeps historical rows consistent without widening any backfill.
        if _sync_value_label(filing):
            json_changed = True
        if not _needs_check(filing, today=today):
            continue
        sec_url = str(filing.get("sec_url") or "")
        if not sec_url.startswith("https://www.sec.gov/"):
            continue
        try:
            document_url = filing_parser.find_primary_document_url(sec_url, expected_form_types=["424B4"])
            soup = filing_parser.fetch_document(document_url)
            cover_text = soup.get_text(" ", strip=True)[:30000]
            authoritative_price = extract_authoritative_final_price(cover_text)
            validate_authoritative_final_price(filing, authoritative_price)
            aggregate = extract_authoritative_aggregate(
                cover_text,
                expected_price=filing.get("offering_price"),
            )
            primary_shares = extract_authoritative_primary_shares(cover_text)
        except OfferingValueReconciliationError:
            raise
        except Exception as error:
            print(f"[offering-value] Warning: could not inspect {filing.get('company')}: {error}")
            continue
        if aggregate is None and primary_shares is None:
            continue
        if reconcile_record(filing, aggregate, primary_shares=primary_shares):
            json_changed = True
            updates[str(filing.get("accession_no") or "")] = {
                "value": filing.get("value"),
                "primary_offering_shares": filing.get("primary_offering_shares"),
                "offering_size_source": filing.get("offering_size_source") or "",
                "offering_size_confidence": filing.get("offering_size_confidence") or "",
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
    if json_changed:
        _atomic_json(path, payload)
    if updates:
        _sync_csv(path.with_suffix(".csv"), updates)
    return updates


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 1:
        raise SystemExit("Usage: python offering_value_reconciler.py <filings.json>")
    reconcile_feed(argv[0])


if __name__ == "__main__":
    main()

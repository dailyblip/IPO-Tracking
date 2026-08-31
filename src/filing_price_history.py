"""Recover authoritative preliminary IPO price ranges for priced public-feed rows.

A final 424B4 can arrive after several S-1/S-1/A amendments. The latest
registration statement is not guaranteed to be the amendment that disclosed the
preliminary range, so a priced row with no filing price must inspect the preceding
registration history before the blank is accepted. Populated filing prices also
need SEC provenance; if that metadata was dropped by an intermediate export, the
same history review restores it rather than silently carrying an unverified value.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date
from pathlib import Path

import dashboard_export
import edgar_client
import filing_parser


class FilingPriceHistoryError(RuntimeError):
    """Raised when required S-1/S-1A history cannot be inspected reliably."""


def _canonical_cik(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.zfill(10) if digits else ""


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _canonical_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def _format_range(low, high):
    def compact(value):
        return f"{float(value):.2f}".rstrip("0").rstrip(".")

    low_text = compact(low)
    high_text = compact(high)
    return low_text if float(low) == float(high) else f"{low_text}-{high_text}"


def _extract_explicit_price_range_from_text(text):
    """Extract tightly anchored preliminary IPO range or fixed-price wording.

    Keep the fallback anchored to expected/estimated IPO price language so fee
    tables, dilution examples, and unrelated dollar values are not treated as
    preliminary pricing. A fixed expected price is represented as low == high.
    """
    text = str(text or "")[:60000]
    number = r"(\d{1,4}(?:\.\d{1,2})?)"
    anchors = (
        r"(?:initial\s+public\s+offering\s+price|"
        r"public\s+offering\s+price|"
        r"offering\s+price|"
        r"price\s+range)"
        r"(?:\s+per\s+share)?"
    )
    patterns = [
        anchors
        + rf"[^$]{{0,180}}?\bbetween\s+\$\s*{number}\s+and\s+\$\s*{number}(?:\s+per\s+share)?",
        anchors
        + rf"[^$]{{0,180}}?\$\s*{number}\s+(?:to|through|[-–—])\s+\$\s*{number}(?:\s+per\s+share)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        low = _number(match.group(1))
        high = _number(match.group(2))
        if low is not None and high is not None and low <= high:
            return {"range_low": low, "range_high": high}

    fixed_patterns = [
        rf"\b(?:we\s+)?expect(?:ed)?\s+(?:that\s+)?(?:the\s+)?initial\s+public\s+offering\s+price"
        rf"(?:\s+per\s+share)?\s+(?:to\s+be|of)\s+\$\s*{number}(?:\s+per\s+share)?",
        rf"\b(?:the\s+)?initial\s+public\s+offering\s+price(?:\s+per\s+share)?"
        rf"\s+is\s+expected\s+to\s+be\s+\$\s*{number}(?:\s+per\s+share)?",
        rf"\bexpected\s+initial\s+public\s+offering\s+price(?:\s+per\s+share)?"
        rf"\s+of\s+\$\s*{number}(?:\s+per\s+share)?",
    ]
    for pattern in fixed_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        price = _number(match.group(1))
        if price is not None:
            return {"range_low": price, "range_high": price}

    return {"range_low": None, "range_high": None}


def _is_priced_row(filing):
    """Return True for every canonical priced lifecycle row.

    Do not require downstream completeness fields here. A priced 424B4 that lost
    pricing_date or final offering_price is itself a data-quality defect; silently
    treating it as outside the history gate would let a blank Filing Price bypass
    the required S-1/S-1A review.
    """
    return (
        str(filing.get("form") or "").strip().upper() == "424B4"
        and str(filing.get("stage") or "").strip().casefold() == "priced"
    )


def _preliminary_price_value(filing):
    return str(filing.get("filing_price") or filing.get("price_range") or "").strip()


def _has_authoritative_price_source(filing):
    source = filing.get("filing_price_source")
    if not isinstance(source, dict):
        return False
    if not bool(
        str(source.get("source") or "").strip().casefold() == "sec edgar"
        and str(source.get("form") or "").strip().upper() in {"S-1", "S-1/A"}
        and str(source.get("filing_date") or "").strip()
        and str(source.get("accession_no") or "").strip()
        and str(source.get("sec_url") or "").strip()
    ):
        return False

    source_date = _canonical_date(source.get("filing_date"))
    pricing_date = _canonical_date(filing.get("pricing_date"))
    if source_date is None or pricing_date is None or source_date > pricing_date:
        return False

    raw_initial_date = str(filing.get("filing_date") or "").strip()
    if raw_initial_date:
        initial_date = _canonical_date(raw_initial_date)
        if initial_date is None or source_date < initial_date:
            return False
    return True


def sec_s1_history(cik, pricing_date):
    """Return S-1/S-1A metadata on or before the authoritative pricing date.

    SEC submissions metadata is authoritative for form, accession, and filing date.
    Results are newest first so the amendment closest to pricing is inspected first,
    while every preceding registration statement remains available as a fallback.
    """
    cik = _canonical_cik(cik)
    if not cik:
        return []
    data = edgar_client._request_json(
        edgar_client.EDGAR_SUBMISSIONS_URL.format(cik=cik),
        edgar_client._get_headers(),
    )
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form") or []
    accessions = recent.get("accessionNumber") or []
    dates = recent.get("filingDate") or []
    history = []
    for form, accession, filed in zip(forms, accessions, dates):
        form = str(form or "").strip().upper()
        filed = str(filed or "").strip()
        accession = str(accession or "").strip()
        if form not in {"S-1", "S-1/A"} or not filed or not accession:
            continue
        if pricing_date and filed > str(pricing_date):
            continue
        history.append({
            "form_type": form,
            "accession_no": accession,
            "filing_date": filed,
        })
    history.sort(key=lambda item: item["filing_date"], reverse=True)
    return history


def parse_s1_history_entry(cik, metadata):
    """Parse one SEC registration filing for its authoritative preliminary price."""
    index_url = edgar_client.build_filing_index_url(cik, metadata["accession_no"])
    document_url = filing_parser.find_primary_document_url(
        index_url,
        expected_form_types=["S-1", "S-1/A"],
    )
    soup = filing_parser.fetch_document(document_url)
    price_range = filing_parser.extract_price_range(soup)
    low = _number((price_range or {}).get("range_low"))
    high = _number((price_range or {}).get("range_high"))
    if low is None or high is None or low > high:
        price_range = _extract_explicit_price_range_from_text(
            soup.get_text(" ", strip=True)
        )
    return {"price_range": price_range}, index_url


def recover_payload_filing_prices(
    payload,
    history_loader=sec_s1_history,
    registration_loader=parse_s1_history_entry,
):
    """Enrich priced rows with an authoritative preliminary price and provenance.

    A priced row is complete only when an existing preliminary price/range has a
    complete, chronologically valid SEC source record. Otherwise every relevant
    S-1/S-1A is inspected from newest to oldest until the latest explicit
    preliminary price is found. This repairs blank Filing Price values, provenance
    metadata lost during later lifecycle/export steps, and stale source dates that
    cannot belong to the priced IPO lifecycle.

    If at least one registration statement is successfully inspected but no reliable
    preliminary price exists, a genuinely blank row remains blank. An already-
    populated but unprovenanced value is release-blocking if SEC history cannot
    verify it; it is safer to stop publication than silently retain unsupported
    pricing metadata.
    """
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("Public feed must contain a filings list")

    updated_payload = dict(payload)
    updated_filings = []
    recovered = 0
    checked = 0

    for filing in filings:
        if not isinstance(filing, dict) or not _is_priced_row(filing):
            updated_filings.append(filing)
            continue

        pricing_date = str(filing.get("pricing_date") or "").strip()
        if not pricing_date:
            raise FilingPriceHistoryError(
                f"Priced row {filing.get('company') or filing.get('id')} has no pricing date for S-1 history review"
            )

        existing_preliminary = _preliminary_price_value(filing)
        if existing_preliminary and _has_authoritative_price_source(filing):
            updated_filings.append(filing)
            continue

        cik = _canonical_cik(filing.get("cik"))
        if not cik:
            raise FilingPriceHistoryError(
                f"Priced row {filing.get('company') or filing.get('id')} has no CIK for S-1 history review"
            )
        history = history_loader(cik, pricing_date)

        # Bound the recovery scan to the current IPO lifecycle. An issuer can have
        # older S-1/S-1A registrations from an abandoned offering or another
        # transaction; those filings must never supply the current IPO's Filing
        # Price merely because they share the same CIK.
        pricing_day = _canonical_date(pricing_date)
        if pricing_day is None:
            raise FilingPriceHistoryError(
                f"Priced row {filing.get('company') or filing.get('id')} has a non-canonical pricing date for S-1 history review"
            )
        raw_initial_date = str(filing.get("filing_date") or "").strip()
        initial_day = _canonical_date(raw_initial_date) if raw_initial_date else None
        if raw_initial_date and initial_day is None:
            raise FilingPriceHistoryError(
                f"Priced row {filing.get('company') or filing.get('id')} has a non-canonical initial filing date for S-1 history review"
            )
        if initial_day is not None and initial_day > pricing_day:
            raise FilingPriceHistoryError(
                f"Priced row {filing.get('company') or filing.get('id')} has an initial filing date after its pricing date"
            )

        lifecycle_history = []
        for metadata in history or []:
            source_day = _canonical_date((metadata or {}).get("filing_date"))
            if source_day is None or source_day > pricing_day:
                continue
            if initial_day is not None and source_day < initial_day:
                continue
            lifecycle_history.append(metadata)
        history = lifecycle_history

        if not history:
            raise FilingPriceHistoryError(
                f"Priced row {filing.get('company') or filing.get('id')} has no S-1/S-1A history inside the current IPO lifecycle"
            )

        checked += 1
        inspected = 0
        found = None
        failures = []
        for metadata in history:
            try:
                parsed, source_url = registration_loader(cik, metadata)
                inspected += 1
            except Exception as error:
                failures.append(f"{metadata.get('accession_no')}: {error}")
                continue

            price_range = (parsed or {}).get("price_range") or {}
            low = _number(price_range.get("range_low"))
            high = _number(price_range.get("range_high"))
            if low is None or high is None or low > high:
                continue
            found = (low, high, metadata, source_url)
            break

        if inspected == 0:
            detail = "; ".join(failures[:3]) or "no registration filing could be parsed"
            raise FilingPriceHistoryError(
                f"Could not inspect S-1/S-1A history for {filing.get('company') or filing.get('id')}: {detail}"
            )

        normalized = dict(filing)
        if found:
            low, high, metadata, source_url = found
            normalized["filing_price"] = _format_range(low, high)
            normalized["filing_price_source"] = {
                "source": "SEC EDGAR",
                "form": metadata.get("form_type"),
                "filing_date": metadata.get("filing_date"),
                "accession_no": metadata.get("accession_no"),
                "sec_url": source_url,
            }
            recovered += 1
        elif existing_preliminary:
            raise FilingPriceHistoryError(
                f"Priced row {filing.get('company') or filing.get('id')} has preliminary price "
                f"{existing_preliminary!r} without recoverable SEC S-1/S-1A provenance"
            )
        updated_filings.append(normalized)

    updated_payload["filings"] = updated_filings
    return updated_payload, recovered, checked


def recover_filing_prices(output_path):
    """Recover preliminary prices in JSON and keep the flattened CSV synchronized."""
    output_path = Path(output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    updated, recovered, checked = recover_payload_filing_prices(payload)
    if updated != payload:
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(updated, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)
        dashboard_export.write_dashboard_csv(updated.get("filings", []), output_path)
    return updated, recovered, checked


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../docs/data/filings.json")
    _, recovered_count, checked_count = recover_filing_prices(target)
    print(
        f"Checked S-1/S-1A history for {checked_count} priced filing(s); "
        f"recovered {recovered_count} preliminary price range(s)/source record(s)"
    )

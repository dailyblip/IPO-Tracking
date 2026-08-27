"""Recover authoritative preliminary IPO price ranges for priced public-feed rows.

A final 424B4 can arrive after several S-1/S-1/A amendments. The latest
registration statement is not guaranteed to be the amendment that disclosed the
preliminary range, so a priced row with no filing price must inspect the preceding
registration history before the blank is accepted.
"""

from __future__ import annotations

import json
import math
import re
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


def _format_range(low, high):
    def compact(value):
        return f"{float(value):.2f}".rstrip("0").rstrip(".")

    return f"{compact(low)}-{compact(high)}"


def _is_priced_row(filing):
    return (
        str(filing.get("form") or "").strip().upper() == "424B4"
        and str(filing.get("stage") or "").strip().casefold() == "priced"
        and filing.get("pricing_date")
        and filing.get("offering_price") not in (None, "")
    )


def _has_preliminary_price(filing):
    return bool(str(filing.get("price_range") or filing.get("filing_price") or "").strip())


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
    """Parse one SEC registration filing using the existing filing parser."""
    index_url = edgar_client.build_filing_index_url(cik, metadata["accession_no"])
    document_url = filing_parser.find_primary_document_url(
        index_url,
        expected_form_types=["S-1", "S-1/A"],
    )
    parsed = filing_parser.parse_filing(document_url, is_range_filing=True)
    return parsed, index_url


def recover_payload_filing_prices(
    payload,
    history_loader=sec_s1_history,
    registration_loader=parse_s1_history_entry,
):
    """Enrich priced rows with an authoritative preliminary range when available.

    A priced row that is already populated is left untouched. For a blank priced row,
    every relevant S-1/S-1A is inspected from newest to oldest until an explicit range
    is found. If at least one registration statement is successfully inspected but no
    reliable range exists, the blank is retained. If none of the required history can
    be inspected, fail closed so the publisher does not silently accept an unverified
    blank.
    """
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("Public feed must contain a filings list")

    updated_payload = dict(payload)
    updated_filings = []
    recovered = 0
    checked = 0

    for filing in filings:
        if not isinstance(filing, dict) or not _is_priced_row(filing) or _has_preliminary_price(filing):
            updated_filings.append(filing)
            continue

        cik = _canonical_cik(filing.get("cik"))
        if not cik:
            raise FilingPriceHistoryError(
                f"Priced row {filing.get('company') or filing.get('id')} has no CIK for S-1 history review"
            )
        history = history_loader(cik, filing.get("pricing_date"))
        if not history:
            raise FilingPriceHistoryError(
                f"Priced row {filing.get('company') or filing.get('id')} has no preceding S-1/S-1A history"
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
        updated_filings.append(normalized)

    updated_payload["filings"] = updated_filings
    return updated_payload, recovered, checked


def recover_filing_prices(output_path):
    """Recover preliminary ranges in JSON and keep the flattened CSV synchronized."""
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
        f"recovered {recovered_count} preliminary price range(s)"
    )

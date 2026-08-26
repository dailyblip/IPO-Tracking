"""Reconcile qualifying S-1 queue records with authoritative final 424B4 filings.

This is a narrow lifecycle handoff safety net for the public Research Monitor feed.
It prevents a company from remaining visibly "Pre-pricing" after the SEC has filed a
final 424B4, while failing closed when final offering size cannot be established.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import dashboard_export
import edgar_client
import filing_parser

MINIMUM_IPO_VALUE = 100_000_000.0


def _canonical_cik(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.zfill(10) if digits else ""


def _share_int(value):
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _money(value):
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    return f"${value:,.0f}"


def extract_final_offering_terms(soup):
    """Read exact final base-offering shares from explicit prospectus language.

    Unlike the ordinary cover parser, this deliberately scans the full document for
    highly specific THE OFFERING labels. Long SEC prospectuses can place that table
    beyond an arbitrary cover-text character window. Generic share counts, shares
    outstanding, and the underwriters' over-allotment option are never used here.
    """
    text = soup.get_text(" ", strip=True)

    primary_match = re.search(
        r"(?:common\s+stock|shares?)\s+offered\s+by\s+(?:us|the\s+company)\s*[:|]?\s*"
        r"([\d,]{4,})\s+shares",
        text,
        re.I,
    )
    secondary_match = re.search(
        r"(?:common\s+stock|shares?)\s+offered\s+by\s+(?:the\s+)?selling\s+"
        r"(?:stockholders|shareholders)\s*[:|]?\s*([\d,]{4,})\s+shares",
        text,
        re.I,
    )
    if primary_match and secondary_match:
        primary = _share_int(primary_match.group(1))
        secondary = _share_int(secondary_match.group(1))
        if primary is not None and secondary is not None:
            return {
                "total_shares": primary + secondary,
                "primary_shares": primary,
                "secondary_shares": secondary,
                "source": "final 424B4 THE OFFERING primary + secondary rows",
                "confidence": "High",
            }

    combined = re.search(
        r"we\s+(?:are|will\s+be)\s+offering\s+([\d,]{4,})\s+shares.{0,2200}?"
        r"selling\s+(?:stockholders|shareholders).{0,1200}?"
        r"(?:are\s+offering|are\s+selling|will\s+sell|offer)(?:\s+an\s+additional)?\s+"
        r"([\d,]{4,})\s+shares",
        text,
        re.I | re.S,
    )
    if combined:
        primary = _share_int(combined.group(1))
        secondary = _share_int(combined.group(2))
        if primary is not None and secondary is not None:
            return {
                "total_shares": primary + secondary,
                "primary_shares": primary,
                "secondary_shares": secondary,
                "source": "final 424B4 explicit issuer + selling-holder blocks",
                "confidence": "High",
            }

    # Issuer-only is safe only when no explicit selling-holder base-offering row exists.
    if primary_match and not secondary_match:
        primary = _share_int(primary_match.group(1))
        if primary is not None:
            return {
                "total_shares": primary,
                "primary_shares": primary,
                "secondary_shares": None,
                "source": "final 424B4 explicit issuer-only THE OFFERING row",
                "confidence": "High",
            }

    return {
        "total_shares": None,
        "primary_shares": None,
        "secondary_shares": None,
        "source": None,
        "confidence": "Unresolved",
    }


def _is_prepricing(filing):
    return (
        str(filing.get("form") or "").upper() in {"S-1", "S-1/A"}
        or str(filing.get("stage") or "").strip().casefold() == "pre-pricing"
    )


def _is_final_priced(filing):
    return (
        str(filing.get("form") or "").upper() == "424B4"
        and str(filing.get("stage") or "").strip().casefold() == "priced"
        and filing.get("offering_price") not in (None, "")
        and filing.get("pricing_date")
    )


def _promote_prepricing_record(record, filing_meta, soup):
    """Build a minimal final record from exact final-prospectus facts, or fail closed."""
    cover = filing_parser.extract_cover_page_data(soup)
    price = cover.get("offering_price")
    terms = extract_final_offering_terms(soup)
    total_shares = terms.get("total_shares")
    if not price or not total_shares:
        return None

    offering_value = float(price) * int(total_shares)
    if offering_value < MINIMUM_IPO_VALUE:
        return None

    pricing_date = str(filing_meta.get("filing_date") or "").strip()
    accession = str(filing_meta.get("accession_no") or "").strip()
    if not pricing_date or not accession:
        return None

    promoted = dict(record)
    old_ticker = str(record.get("ticker") or "").strip().upper()
    final_ticker = str(cover.get("ticker") or filing_meta.get("ticker") or old_ticker).strip().upper()

    promoted.update({
        "id": accession,
        "accession_no": accession,
        "form": "424B4",
        "stage": "Priced",
        "filed": pricing_date,
        "pricing_date": pricing_date,
        "offering_price": float(price),
        "value": offering_value,
        "value_label": _money(offering_value),
        "primary_offering_shares": terms.get("primary_shares"),
        "secondary_offering_shares": terms.get("secondary_shares"),
        "offering_size_source": terms.get("source"),
        "offering_size_confidence": terms.get("confidence"),
        "ticker": final_ticker,
        "people": [],
        "people_count": 0,
        "signals": [
            f"Offering priced at ${float(price):.2f} per share",
            f"Offering raised approximately {_money(offering_value)}",
            "Final 424B4 supersedes the pre-pricing registration record",
        ],
        "sec_url": edgar_client.build_filing_index_url(
            _canonical_cik(filing_meta.get("cik") or record.get("cik")), accession
        ),
    })

    # A quote captured for the pre-pricing row may be retained only after the final
    # filing itself confirms the same ticker. Otherwise fail closed on market data.
    if not final_ticker or final_ticker != old_ticker:
        promoted.pop("current_price", None)
        promoted.pop("price_updated", None)

    # A pre-pricing ownership view is not evidence of final post-IPO liquidity.
    for key in (
        "lockup_end_date", "lockup_duration_days", "lockup_duration_value",
        "lockup_duration_unit", "lockup_text", "lockup_scope", "lockup_terms",
        "lockup_confidence",
    ):
        promoted.pop(key, None)

    filing_date = str(promoted.get("filing_date") or "").strip()
    if filing_date and filing_date > pricing_date:
        promoted["filing_date"] = None
    return promoted


def reconcile_payload(payload, final_filings, soup_loader):
    """Reconcile stale S-1 records against final 424B4 metadata by SEC CIK."""
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("Public feed must contain a filings list")

    final_by_cik = {}
    for meta in final_filings:
        cik = _canonical_cik(meta.get("cik"))
        if not cik:
            continue
        prior = final_by_cik.get(cik)
        if prior is None or str(meta.get("filing_date") or "") > str(prior.get("filing_date") or ""):
            final_by_cik[cik] = meta

    already_priced = {
        _canonical_cik(filing.get("cik"))
        for filing in filings
        if isinstance(filing, dict) and _is_final_priced(filing)
    }

    reconciled = []
    promoted_count = removed_count = 0
    for filing in filings:
        if not isinstance(filing, dict) or not _is_prepricing(filing):
            reconciled.append(filing)
            continue
        cik = _canonical_cik(filing.get("cik"))
        final_meta = final_by_cik.get(cik)
        if not final_meta:
            reconciled.append(filing)
            continue
        if cik in already_priced:
            removed_count += 1
            continue

        try:
            soup = soup_loader(final_meta)
            promoted = _promote_prepricing_record(filing, final_meta, soup)
        except Exception as error:
            print(f"[lifecycle_reconciler] Could not verify final terms for CIK {cik}: {error}")
            promoted = None

        if promoted is None:
            # A final 424B4 proves the issuer is no longer pre-pricing. If exact
            # qualifying final size is unresolved, the contract requires omission
            # rather than publication of a stale or guessed record.
            removed_count += 1
            continue
        reconciled.append(promoted)
        promoted_count += 1

    payload = dict(payload)
    payload["filings"] = reconciled
    if promoted_count or removed_count:
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    return payload, promoted_count, removed_count


def _load_final_soup(meta):
    index_url = edgar_client.build_filing_index_url(meta["cik"], meta["accession_no"])
    document_url = filing_parser.find_primary_document_url(index_url, expected_form_types=["424B4"])
    return filing_parser.fetch_document(document_url)


def reconcile_feed(output_path, days_back=60):
    output_path = Path(output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    if not any(_is_prepricing(f) for f in payload.get("filings", []) if isinstance(f, dict)):
        dashboard_export.write_dashboard_csv(payload.get("filings", []), output_path)
        return payload, 0, 0

    final_filings = edgar_client.find_recent_424b4_filings(days_back=days_back)
    payload, promoted, removed = reconcile_payload(payload, final_filings, _load_final_soup)
    if promoted or removed:
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(output_path)
    dashboard_export.write_dashboard_csv(payload.get("filings", []), output_path)
    return payload, promoted, removed


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../docs/data/filings.json")
    _, promoted_count, removed_count = reconcile_feed(target)
    print(
        f"Lifecycle reconciliation promoted {promoted_count} final 424B4 record(s) "
        f"and removed {removed_count} stale pre-pricing record(s)."
    )

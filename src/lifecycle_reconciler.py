"""Reconcile qualifying S-1 queue records with authoritative final 424B4 filings.

This is a narrow lifecycle handoff safety net for the public Research Monitor feed.
It prevents an issuer from remaining visibly pre-pricing after the SEC has filed a
final 424B4, and repairs incomplete final records when exact final offering terms
are present later in a long prospectus. A confirmed priced operating-company IPO
may remain visible with offering size blank when exact size cannot be established.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import dashboard_export
import edgar_client
import filing_parser


def _canonical_cik(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.zfill(10) if digits else ""


def _share_int(value):
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _number(value):
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
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


def _is_final_record(filing):
    return str(filing.get("form") or "").upper() == "424B4"


def _is_final_priced(filing):
    return (
        _is_final_record(filing)
        and str(filing.get("stage") or "").strip().casefold() == "priced"
        and filing.get("offering_price") not in (None, "")
        and filing.get("pricing_date")
    )


def _has_release_grade_final_size(filing):
    """Return True when an already-priced row has a verified populated size."""
    value = _number(filing.get("value"))
    return (
        _is_final_priced(filing)
        and value is not None
        and value > 0
        and str(filing.get("offering_size_confidence") or "").strip().casefold() == "high"
        and bool(str(filing.get("offering_size_source") or "").strip())
    )


def _apply_final_terms(record, filing_meta, soup):
    """Apply authoritative SEC final terms without fabricating unavailable size facts."""
    cover = filing_parser.extract_cover_page_data(soup)
    price = cover.get("offering_price")
    terms = extract_final_offering_terms(soup)
    total_shares = terms.get("total_shares")
    if not price:
        return None

    offering_value = float(price) * int(total_shares) if total_shares else None
    pricing_date = str(filing_meta.get("filing_date") or record.get("pricing_date") or "").strip()
    accession = str(filing_meta.get("accession_no") or record.get("accession_no") or "").strip()
    if not pricing_date or not accession:
        return None

    updated = dict(record)
    old_ticker = str(record.get("ticker") or "").strip().upper()
    final_ticker = str(cover.get("ticker") or filing_meta.get("ticker") or old_ticker).strip().upper()

    updated.update({
        "id": accession,
        "accession_no": accession,
        "form": "424B4",
        "stage": "Priced",
        "filed": pricing_date,
        "pricing_date": pricing_date,
        "offering_price": float(price),
        "value": offering_value,
        "value_label": _money(offering_value) if offering_value is not None else None,
        "primary_offering_shares": terms.get("primary_shares"),
        "secondary_offering_shares": terms.get("secondary_shares"),
        "offering_size_source": terms.get("source"),
        "offering_size_confidence": terms.get("confidence"),
        "ticker": final_ticker,
        "sec_url": edgar_client.build_filing_index_url(
            _canonical_cik(filing_meta.get("cik") or record.get("cik")), accession
        ),
    })

    # Existing market data is safe to carry across the lifecycle handoff only when
    # the final SEC prospectus confirms the same ticker identity.
    if not final_ticker or final_ticker != old_ticker:
        updated.pop("current_price", None)
        updated.pop("price_updated", None)

    filing_date = str(updated.get("filing_date") or "").strip()
    if filing_date and filing_date > pricing_date:
        updated["filing_date"] = None
    return updated


def _final_signals(record, price, value):
    keep = []
    for signal in record.get("signals") or []:
        text = str(signal or "").strip()
        lowered = text.casefold()
        if not text:
            continue
        if lowered.startswith("offering priced at"):
            continue
        if lowered.startswith("offering raised approximately"):
            continue
        if "remains pre-pricing" in lowered or "registration statement amended" in lowered:
            continue
        keep.append(text)
    final = [f"Offering priced at ${float(price):.2f} per share"]
    if value is not None:
        final.append(f"Offering raised approximately {_money(value)}")
    for signal in keep:
        if signal not in final:
            final.append(signal)
    return final


def _repair_final_record(record, filing_meta, soup):
    """Repair an incomplete 424B4 row while preserving final-filing research details."""
    repaired = _apply_final_terms(record, filing_meta, soup)
    if repaired is None:
        return None
    repaired["signals"] = _final_signals(
        repaired, repaired["offering_price"], repaired["value"]
    )
    return repaired


def _promote_prepricing_record(record, filing_meta, soup):
    """Build a minimal final record from authoritative final-prospectus facts."""
    promoted = _apply_final_terms(record, filing_meta, soup)
    if promoted is None:
        return None

    # A pre-pricing ownership snapshot is not evidence of final post-IPO ownership or
    # liquidity. The fallback handoff deliberately removes those fields rather than
    # carrying preliminary facts into a final record.
    promoted["people"] = []
    promoted["people_count"] = 0
    for key in (
        "lockup_end_date", "lockup_duration_days", "lockup_duration_value",
        "lockup_duration_unit", "lockup_text", "lockup_scope", "lockup_terms",
        "lockup_confidence",
    ):
        promoted.pop(key, None)
    promoted["signals"] = _final_signals(
        promoted, promoted["offering_price"], promoted["value"]
    )
    if "Final 424B4 supersedes the pre-pricing registration record" not in promoted["signals"]:
        promoted["signals"].append("Final 424B4 supersedes the pre-pricing registration record")
    return promoted


def _select_final_meta(candidates, existing_final=None, prepricing=None):
    """Select the IPO final prospectus, avoiding a later follow-on 424B4 when possible."""
    if not candidates:
        return None
    candidates = sorted(candidates, key=lambda item: str(item.get("filing_date") or ""))

    accession = str((existing_final or {}).get("accession_no") or "").strip()
    if accession:
        for candidate in candidates:
            if str(candidate.get("accession_no") or "").strip() == accession:
                return candidate

    prepricing_date = str(
        (prepricing or {}).get("filed")
        or (prepricing or {}).get("filing_date")
        or ""
    ).strip()
    if prepricing_date:
        eligible = [
            candidate for candidate in candidates
            if str(candidate.get("filing_date") or "") >= prepricing_date
        ]
        if eligible:
            return eligible[0]

    return candidates[0]


def reconcile_payload(payload, final_filings, soup_loader):
    """Reconcile stale/incomplete lifecycle rows against SEC 424B4 metadata by CIK."""
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("Public feed must contain a filings list")

    finals_by_cik = {}
    for meta in final_filings:
        cik = _canonical_cik(meta.get("cik"))
        if cik:
            finals_by_cik.setdefault(cik, []).append(meta)

    prepricing_by_cik = {}
    final_record_by_cik = {}
    for filing in filings:
        if not isinstance(filing, dict):
            continue
        cik = _canonical_cik(filing.get("cik"))
        if not cik:
            continue
        if _is_prepricing(filing):
            prepricing_by_cik.setdefault(cik, filing)
        elif _is_final_record(filing):
            final_record_by_cik.setdefault(cik, filing)

    states = {}
    repaired_count = 0
    for cik in set(prepricing_by_cik) | set(final_record_by_cik):
        candidates = finals_by_cik.get(cik) or []
        if not candidates:
            continue
        existing_final = final_record_by_cik.get(cik)
        prepricing = prepricing_by_cik.get(cik)
        final_meta = _select_final_meta(candidates, existing_final, prepricing)
        if not final_meta:
            continue

        if existing_final is not None:
            if _has_release_grade_final_size(existing_final):
                states[cik] = {
                    "meta": final_meta,
                    "existing": existing_final,
                    "replacement": existing_final,
                }
                continue
            try:
                soup = soup_loader(final_meta)
                replacement = _repair_final_record(existing_final, final_meta, soup)
            except Exception as error:
                print(f"[lifecycle_reconciler] Could not repair final terms for CIK {cik}: {error}")
                replacement = None
            states[cik] = {
                "meta": final_meta,
                "existing": existing_final,
                "replacement": replacement,
            }
            if replacement is not None:
                repaired_count += 1
            continue

        if prepricing is not None:
            try:
                soup = soup_loader(final_meta)
                replacement = _promote_prepricing_record(prepricing, final_meta, soup)
            except Exception as error:
                print(f"[lifecycle_reconciler] Could not verify final terms for CIK {cik}: {error}")
                replacement = None
            states[cik] = {
                "meta": final_meta,
                "existing": None,
                "replacement": replacement,
            }
            if replacement is not None:
                repaired_count += 1

    reconciled = []
    removed_count = 0
    inserted_promotions = set()
    for filing in filings:
        if not isinstance(filing, dict):
            reconciled.append(filing)
            continue
        cik = _canonical_cik(filing.get("cik"))
        state = states.get(cik)
        if state is None:
            reconciled.append(filing)
            continue

        if _is_prepricing(filing):
            removed_count += 1
            if state["existing"] is None and state["replacement"] is not None and cik not in inserted_promotions:
                reconciled.append(state["replacement"])
                inserted_promotions.add(cik)
            continue

        if _is_final_record(filing) and filing is state["existing"]:
            if state["replacement"] is not None:
                reconciled.append(state["replacement"])
            else:
                # A final 424B4 proves the issuer is no longer pre-pricing. If the
                # final price itself remains unresolved, omit rather than guess.
                removed_count += 1
            continue

        reconciled.append(filing)

    payload = dict(payload)
    payload["filings"] = reconciled
    if repaired_count or removed_count:
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    return payload, repaired_count, removed_count


def _load_final_soup(meta):
    index_url = edgar_client.build_filing_index_url(meta["cik"], meta["accession_no"])
    document_url = filing_parser.find_primary_document_url(index_url, expected_form_types=["424B4"])
    return filing_parser.fetch_document(document_url)


def reconcile_feed(output_path, days_back=60):
    output_path = Path(output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    filings = [f for f in payload.get("filings", []) if isinstance(f, dict)]
    needs_reconciliation = any(
        _is_prepricing(filing)
        or (_is_final_record(filing) and not _has_release_grade_final_size(filing))
        for filing in filings
    )
    if not needs_reconciliation:
        dashboard_export.write_dashboard_csv(payload.get("filings", []), output_path)
        return payload, 0, 0

    final_filings = edgar_client.find_recent_424b4_filings(days_back=days_back)
    payload, repaired, removed = reconcile_payload(payload, final_filings, _load_final_soup)
    if repaired or removed:
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(output_path)
    dashboard_export.write_dashboard_csv(payload.get("filings", []), output_path)
    return payload, repaired, removed


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../docs/data/filings.json")
    _, repaired_count, removed_count = reconcile_feed(target)
    print(
        f"Lifecycle reconciliation repaired/promoted {repaired_count} final 424B4 record(s) "
        f"and removed {removed_count} stale/unresolved record(s)."
    )

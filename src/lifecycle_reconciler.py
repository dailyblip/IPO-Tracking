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
import final_pricing_release_gate


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


def _final_metadata_ticker_mismatch(filing, filing_meta):
    """Return True when authoritative SEC final metadata contradicts stored ticker."""
    sec_ticker = str(filing_meta.get("ticker") or "").strip().upper()
    stored_ticker = str(filing.get("ticker") or "").strip().upper()
    return bool(sec_ticker and sec_ticker != stored_ticker)


def _can_preserve_release_grade_final(filing, filing_meta):
    """Keep an already-valid final when only optional size repair is unavailable.

    Offering size is not a release requirement. A transient SEC document failure or
    an unparseable exact share count must therefore not delete a priced IPO whose
    final price/date state is already release-grade. An SEC ticker contradiction is
    still release-blocking and must be repaired rather than preserved.
    """
    return (
        final_pricing_release_gate.is_release_grade_final(filing)
        and not _final_metadata_ticker_mismatch(filing, filing_meta)
    )


def _clear_market_quote_derivatives(record):
    """Clear market values when final SEC ticker identity changes.

    A final-ticker change invalidates not only the top-level Current Price but every
    person-level value derived from that quote. Preserve SEC ownership facts while
    removing quote-derived economics and market-value signals so a stale symbol can
    never survive lifecycle repair indirectly through beneficial-owner fields.
    """
    record.pop("current_price", None)
    record.pop("price_updated", None)

    people = record.get("people")
    if isinstance(people, list):
        cleaned_people = []
        for person in people:
            if not isinstance(person, dict):
                cleaned_people.append(person)
                continue
            cleaned = dict(person)
            for field in ("cash_value", "liquid_value", "locked_value", "valuation_as_of"):
                cleaned.pop(field, None)
            cleaned_people.append(cleaned)
        record["people"] = cleaned_people

    signals = record.get("signals")
    if isinstance(signals, list):
        record["signals"] = [
            signal
            for signal in signals
            if not (
                isinstance(signal, str)
                and (
                    "currently valued at approximately" in signal.casefold()
                    or "current market value" in signal.casefold()
                )
            )
        ]
    return record


def _reconcile_person_ipo_price_derivatives(record):
    """Keep existing person IPO-value fields aligned with the authoritative final price.

    ``ipo_value`` and ``cash_realized_ipo`` are arithmetic derivatives of SEC share
    quantities and the final IPO price. If lifecycle repair corrects that price,
    preserving an existing value calculated from an older price would publish
    inconsistent economics. Recompute only an already-published derivative when its
    supporting share quantity exists; otherwise remove that stale value. Do not add
    new person-level economics solely because a lifecycle repair has enough inputs.
    """
    price = _number(record.get("offering_price"))
    people = record.get("people")
    if price is None or price <= 0 or not isinstance(people, list):
        return record

    normalized_people = []
    for person in people:
        if not isinstance(person, dict):
            normalized_people.append(person)
            continue
        normalized = dict(person)

        if "ipo_value" in person:
            shares = _number(person.get("shares"))
            if shares is None or shares < 0:
                normalized.pop("ipo_value", None)
            else:
                normalized["ipo_value"] = shares * price

        if "cash_realized_ipo" in person:
            shares_sold = _number(person.get("shares_sold_ipo"))
            if shares_sold is None or shares_sold < 0:
                normalized.pop("cash_realized_ipo", None)
            else:
                normalized["cash_realized_ipo"] = shares_sold * price
        normalized_people.append(normalized)

    record["people"] = normalized_people
    return record


def _resolved_offering_size_fields(record, price, terms):
    """Prefer newly verified final size, otherwise preserve only supported prior size.

    Lifecycle repair may successfully verify final price while a conservative parser
    cannot re-extract exact share counts from the same 424B4. That optional failure
    must not erase an already evidence-supported offering size. When the final price
    changes, recompute value only from preserved public share quantities; a standalone
    old value is cleared because carrying it forward would make it stale arithmetic.
    """
    total_shares = _share_int(terms.get("total_shares"))
    if total_shares is not None and total_shares > 0:
        value = float(price) * total_shares
        return {
            "value": value,
            "value_label": _money(value),
            "primary_offering_shares": terms.get("primary_shares"),
            "secondary_offering_shares": terms.get("secondary_shares"),
            "offering_size_source": terms.get("source"),
            "offering_size_confidence": terms.get("confidence"),
            "offering_size_conflict": False,
        }

    source = str(record.get("offering_size_source") or "").strip()
    confidence = str(record.get("offering_size_confidence") or "").strip()
    conflict = bool(record.get("offering_size_conflict"))
    supported = bool(
        source
        and confidence
        and confidence.casefold() != "unresolved"
        and not conflict
    )
    primary = _share_int(record.get("primary_offering_shares"))
    secondary = _share_int(record.get("secondary_offering_shares"))

    if supported and (primary is not None or secondary is not None):
        preserved_total = (primary or 0) + (secondary or 0)
        if preserved_total > 0:
            value = float(price) * preserved_total
            return {
                "value": value,
                "value_label": _money(value),
                "primary_offering_shares": primary,
                "secondary_offering_shares": secondary,
                "offering_size_source": source,
                "offering_size_confidence": confidence,
                "offering_size_conflict": False,
            }

    existing_value = _number(record.get("value"))
    existing_price = _number(record.get("offering_price"))
    if (
        supported
        and existing_value is not None
        and existing_value > 0
        and existing_price is not None
        and abs(existing_price - float(price)) < 1e-9
    ):
        return {
            "value": existing_value,
            "value_label": _money(existing_value),
            "primary_offering_shares": primary,
            "secondary_offering_shares": secondary,
            "offering_size_source": source,
            "offering_size_confidence": confidence,
            "offering_size_conflict": False,
        }

    return {
        "value": None,
        "value_label": None,
        "primary_offering_shares": None,
        "secondary_offering_shares": None,
        "offering_size_source": None,
        "offering_size_confidence": "Unresolved",
        "offering_size_conflict": conflict,
    }


def _apply_final_terms(record, filing_meta, soup):
    """Apply authoritative SEC final terms without fabricating unavailable size facts."""
    cover = filing_parser.extract_cover_page_data(soup)
    price = cover.get("offering_price")
    terms = extract_final_offering_terms(soup)
    if not price:
        return None

    price = float(price)
    size_fields = _resolved_offering_size_fields(record, price, terms)
    final_filed = str(filing_meta.get("filing_date") or "").strip()
    # The SEC 424B4 filing date is not itself evidence of the IPO Pricing Date.
    # Preserve a date only on an already-final row; newly promoted S-1/S-1A rows
    # remain blank until pricing_date_reconciler verifies the final prospectus date.
    pricing_date = (
        str(record.get("pricing_date") or "").strip()
        if _is_final_record(record)
        else ""
    )
    accession = str(filing_meta.get("accession_no") or record.get("accession_no") or "").strip()
    if not final_filed or not accession:
        return None

    updated = dict(record)
    old_ticker = str(record.get("ticker") or "").strip().upper()
    final_ticker = str(cover.get("ticker") or filing_meta.get("ticker") or old_ticker).strip().upper()

    updated.update({
        "id": accession,
        "accession_no": accession,
        "form": "424B4",
        "stage": "Priced",
        "filed": final_filed,
        "pricing_date": pricing_date or None,
        "offering_price": price,
        **size_fields,
        "ticker": final_ticker,
        "sec_url": edgar_client.build_filing_index_url(
            _canonical_cik(filing_meta.get("cik") or record.get("cik")), accession
        ),
    })
    # The conflict flag is an internal parser/reconciliation diagnostic. It is
    # intentionally excluded from the registered public V1 feed schema.
    updated.pop("offering_size_conflict", None)
    _reconcile_person_ipo_price_derivatives(updated)

    # Existing market data is safe to carry across the lifecycle handoff only when
    # the final SEC prospectus confirms the same ticker identity. A mismatch clears
    # both the quote and every holder value derived from that stale quote.
    if not final_ticker or final_ticker != old_ticker:
        _clear_market_quote_derivatives(updated)

    filing_date = str(updated.get("filing_date") or "").strip()
    if filing_date and pricing_date and filing_date > pricing_date:
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

    # A pre-pricing quote is never evidence of the post-IPO market price, even when
    # the final prospectus confirms the same ticker. A reused/already-trading symbol
    # can therefore not survive the S-1 -> 424B4 handoff as Current Price. The normal
    # priced-IPO quote refresh may repopulate it later from a verified final state.
    promoted.pop("current_price", None)
    promoted.pop("price_updated", None)
    promoted["signals"] = [
        signal
        for signal in promoted.get("signals") or []
        if not (
            isinstance(signal, str)
            and (
                "currently valued at approximately" in signal.casefold()
                or "current market value" in signal.casefold()
            )
        )
    ]

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
        return None

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
            ticker_mismatch = _final_metadata_ticker_mismatch(existing_final, final_meta)
            if _has_release_grade_final_size(existing_final) and not ticker_mismatch:
                states[cik] = {
                    "meta": final_meta,
                    "existing": existing_final,
                    "replacement": existing_final,
                }
                continue

            preserve_existing = _can_preserve_release_grade_final(existing_final, final_meta)
            try:
                soup = soup_loader(final_meta)
                replacement = _repair_final_record(existing_final, final_meta, soup)
            except Exception as error:
                print(f"[lifecycle_reconciler] Could not repair final terms for CIK {cik}: {error}")
                replacement = existing_final if preserve_existing else None

            # Exact offering size is optional. If the final prospectus cannot be
            # reparsed well enough to improve size, retain an already release-grade
            # priced row unless SEC metadata says its ticker identity is stale.
            if replacement is None and preserve_existing:
                replacement = existing_final

            if replacement is not None and replacement == existing_final:
                replacement = existing_final

            states[cik] = {
                "meta": final_meta,
                "existing": existing_final,
                "replacement": replacement,
            }
            if replacement is not None and replacement is not existing_final:
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
    # Every final row gets a cheap SEC metadata identity check. The full 424B4 is
    # refetched only when final terms are incomplete or authoritative metadata
    # contradicts the stored ticker.
    needs_reconciliation = any(
        _is_prepricing(filing) or _is_final_record(filing)
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

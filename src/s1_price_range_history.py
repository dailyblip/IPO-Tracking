"""Recover missing pre-pricing IPO ranges from authoritative SEC registration history.

The S-1 monitor parses the newest filing in isolation. An amendment can omit a
range that was publicly disclosed in an earlier S-1/S-1A from the same
registration statement, so a blank Filing Price must not be accepted until that
exact SEC registration lineage has been reviewed.

This module recovers only non-degenerate price ranges. Fixed/point prices remain
the responsibility of ``s1_preliminary_price_gate.py`` so this history pass cannot
weaken its stricter cover-page validation.
"""

from __future__ import annotations

import json
import math
import re
import sys
from datetime import date
from pathlib import Path

import dashboard_export
import filing_price_history


FORMS = {"S-1", "S-1/A"}


class S1PriceRangeHistoryError(RuntimeError):
    """Raised when required SEC range history cannot be reviewed safely."""


def _canonical_cik(value) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.zfill(10) if digits else ""


def _canonical_accession(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _canonical_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _nondegenerate_range(parsed):
    price_range = (parsed or {}).get("price_range") or {}
    low = _number(price_range.get("range_low"))
    high = _number(price_range.get("range_high"))
    if low is None or high is None or low >= high:
        return None
    return low, high


def _format_range(low, high) -> str:
    return f"${float(low):,.2f}–${float(high):,.2f}"


def _is_blank_prepricing_row(filing) -> bool:
    if not isinstance(filing, dict):
        return False
    if str(filing.get("form") or "").strip().upper() not in FORMS:
        return False
    if str(filing.get("stage") or "").strip().casefold() != "pre-pricing":
        return False
    return not str(
        filing.get("filing_price") or filing.get("price_range") or ""
    ).strip()


def _current_history_row(filing, history):
    cik = _canonical_cik(filing.get("cik"))
    accession = _canonical_accession(
        filing.get("accession_no") or filing.get("id")
    )
    filed_day = _canonical_date(filing.get("filed"))
    form = str(filing.get("form") or "").strip().upper()

    if not cik or not accession:
        raise S1PriceRangeHistoryError(
            f"{filing.get('company') or filing.get('id')}: blank pre-pricing Filing Price lacks exact SEC identity"
        )
    if filed_day is None:
        raise S1PriceRangeHistoryError(
            f"{filing.get('company') or filing.get('id')}: blank pre-pricing Filing Price has a non-canonical filing date"
        )

    matches = [
        metadata
        for metadata in history or []
        if isinstance(metadata, dict)
        and _canonical_accession(metadata.get("accession_no")) == accession
    ]
    if len(matches) != 1:
        raise S1PriceRangeHistoryError(
            f"{filing.get('company') or filing.get('id')}: current S-1/S-1A does not resolve to one exact SEC history row"
        )

    current = matches[0]
    if str(current.get("form_type") or "").strip().upper() != form:
        raise S1PriceRangeHistoryError(
            f"{filing.get('company') or filing.get('id')}: current SEC registration form does not match the published row"
        )
    if _canonical_date(current.get("filing_date")) != filed_day:
        raise S1PriceRangeHistoryError(
            f"{filing.get('company') or filing.get('id')}: current SEC registration date does not match the published row"
        )
    if not str(current.get("file_number") or "").strip():
        raise S1PriceRangeHistoryError(
            f"{filing.get('company') or filing.get('id')}: current SEC S-1/S-1A lacks registration file-number lineage"
        )
    return current


def _parse_history_range(cik, metadata, registration_loader):
    try:
        parsed, index_url = registration_loader(cik, metadata)
    except Exception as error:
        raise S1PriceRangeHistoryError(
            f"Could not inspect SEC {metadata.get('form_type') or 'S-1'} "
            f"{metadata.get('accession_no') or '<unknown accession>'} for preliminary price history: {error}"
        ) from error
    return _nondegenerate_range(parsed), index_url


def _source(metadata, index_url):
    return {
        "source": "SEC EDGAR",
        "form": str(metadata.get("form_type") or "").strip().upper(),
        "filing_date": str(metadata.get("filing_date") or "").strip(),
        "accession_no": str(metadata.get("accession_no") or "").strip(),
        "file_number": str(metadata.get("file_number") or "").strip(),
        "sec_url": str(index_url or "").strip(),
    }


def _apply_range(filing, price_range, metadata, index_url):
    low, high = price_range
    label = _format_range(low, high)
    updated = dict(filing)
    updated["price_range"] = label
    updated["filing_price"] = label
    updated["filing_price_source"] = _source(metadata, index_url)
    updated["priority"] = "High"

    signals = [
        signal
        for signal in updated.get("signals") or []
        if str(signal or "")
        != "No preliminary price range or fixed offering price detected yet"
        and not str(signal or "").startswith("Preliminary offering range disclosed at ")
    ]
    signals.append(f"Preliminary offering range disclosed at {label}")
    if _canonical_accession(metadata.get("accession_no")) != _canonical_accession(
        filing.get("accession_no") or filing.get("id")
    ):
        signals.append(
            "Filing Price carried from SEC registration history dated "
            f"{metadata.get('filing_date')}"
        )
    updated["signals"] = signals
    return updated


def _recover_one(
    filing,
    *,
    history_loader=filing_price_history.sec_s1_history,
    registration_loader=filing_price_history.parse_s1_history_entry,
):
    if not _is_blank_prepricing_row(filing):
        return filing, False

    cik = _canonical_cik(filing.get("cik"))
    filed_day = _canonical_date(filing.get("filed"))
    if not cik or filed_day is None:
        # _current_history_row gives a more specific release-blocking message.
        history = []
    else:
        try:
            history = history_loader(cik, filed_day.isoformat())
        except Exception as error:
            raise S1PriceRangeHistoryError(
                f"Could not load SEC S-1/S-1A history for "
                f"{filing.get('company') or filing.get('id')}: {error}"
            ) from error

    current = _current_history_row(filing, history)
    file_number = str(current.get("file_number") or "").strip()

    lineage = [
        metadata
        for metadata in history or []
        if isinstance(metadata, dict)
        and str(metadata.get("file_number") or "").strip() == file_number
        and _canonical_date(metadata.get("filing_date")) is not None
        and _canonical_date(metadata.get("filing_date")) <= filed_day
    ]
    if not lineage:
        raise S1PriceRangeHistoryError(
            f"{filing.get('company') or filing.get('id')}: no same-registration S-1/S-1A history was available"
        )

    # The exact current amendment is authoritative and does not require any
    # chronology inference.
    current_range, current_url = _parse_history_range(cik, current, registration_loader)
    if current_range is not None:
        return _apply_range(filing, current_range, current, current_url), True

    current_accession = _canonical_accession(current.get("accession_no"))

    # Another same-registration filing on the exact same day cannot safely be
    # ordered relative to the current amendment from date-only SEC metadata. If
    # it discloses a range, fail closed rather than guessing that it preceded the
    # current blank amendment.
    same_day_others = [
        metadata
        for metadata in lineage
        if _canonical_date(metadata.get("filing_date")) == filed_day
        and _canonical_accession(metadata.get("accession_no")) != current_accession
    ]
    for metadata in same_day_others:
        candidate_range, _ = _parse_history_range(cik, metadata, registration_loader)
        if candidate_range is not None:
            raise S1PriceRangeHistoryError(
                f"{filing.get('company') or filing.get('id')}: same-day SEC S-1/S-1A range "
                "cannot be ordered relative to the current amendment"
            )

    by_day = {}
    for metadata in lineage:
        source_day = _canonical_date(metadata.get("filing_date"))
        if source_day is None or source_day >= filed_day:
            continue
        by_day.setdefault(source_day, []).append(metadata)

    for source_day in sorted(by_day, reverse=True):
        parsed_ranges = []
        for metadata in by_day[source_day]:
            candidate_range, index_url = _parse_history_range(
                cik, metadata, registration_loader
            )
            if candidate_range is not None:
                parsed_ranges.append((candidate_range, metadata, index_url))

        if not parsed_ranges:
            continue

        unique_ranges = {item[0] for item in parsed_ranges}
        if len(unique_ranges) != 1:
            raise S1PriceRangeHistoryError(
                f"{filing.get('company') or filing.get('id')}: conflicting preliminary ranges "
                f"were disclosed in same-day SEC registration history on {source_day.isoformat()}"
            )

        # Every supporting filing on this day states the same range, so any exact
        # source accession is valid provenance. Pick a deterministic one without
        # inferring intra-day chronology.
        parsed_ranges.sort(
            key=lambda item: _canonical_accession(item[1].get("accession_no"))
        )
        candidate_range, metadata, index_url = parsed_ranges[0]
        return _apply_range(
            filing, candidate_range, metadata, index_url
        ), True

    return filing, False


def recover_payload_prepricing_ranges(
    payload,
    *,
    history_loader=filing_price_history.sec_s1_history,
    registration_loader=filing_price_history.parse_s1_history_entry,
):
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("S-1 watch payload must contain a filings list")

    updated = dict(payload)
    updated_filings = []
    recovered = 0
    for filing in filings:
        repaired, changed = _recover_one(
            filing,
            history_loader=history_loader,
            registration_loader=registration_loader,
        )
        updated_filings.append(repaired)
        recovered += int(changed)
    updated["filings"] = updated_filings
    return updated, recovered


def synchronize_queue_ranges(queue_payload, watch_payload):
    watch_by_identity = {}
    for filing in watch_payload.get("filings") or []:
        if not isinstance(filing, dict):
            continue
        cik = _canonical_cik(filing.get("cik"))
        accession = _canonical_accession(
            filing.get("accession_no") or filing.get("id")
        )
        if cik and accession:
            watch_by_identity[(cik, accession)] = filing

    updated = dict(queue_payload)
    updated_filings = []
    changed = 0
    for filing in queue_payload.get("filings") or []:
        if not isinstance(filing, dict):
            updated_filings.append(filing)
            continue
        key = (
            _canonical_cik(filing.get("cik")),
            _canonical_accession(filing.get("accession_no")),
        )
        watch = watch_by_identity.get(key)
        if not watch or not str(watch.get("filing_price") or "").strip():
            updated_filings.append(filing)
            continue

        repaired = dict(filing)
        for field in (
            "price_range",
            "filing_price",
            "filing_price_source",
            "priority",
            "signals",
        ):
            repaired[field] = watch.get(field)
        changed += int(repaired != filing)
        updated_filings.append(repaired)

    updated["filings"] = updated_filings
    return updated, changed


def _load_payload(path):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise S1PriceRangeHistoryError(f"Could not read {path}: {error}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("filings"), list):
        raise S1PriceRangeHistoryError(f"{path} is not a valid Research Monitor feed")
    return payload


def _write_payload(path, payload):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def repair_files(watch_path, queue_path):
    watch_path = Path(watch_path)
    queue_path = Path(queue_path)
    watch_payload = _load_payload(watch_path)
    queue_payload = _load_payload(queue_path)

    repaired_watch, recovered = recover_payload_prepricing_ranges(watch_payload)
    repaired_queue, queue_changed = synchronize_queue_ranges(
        queue_payload, repaired_watch
    )

    if repaired_watch != watch_payload:
        _write_payload(watch_path, repaired_watch)
    if repaired_queue != queue_payload:
        _write_payload(queue_path, repaired_queue)
        dashboard_export.write_dashboard_csv(
            repaired_queue.get("filings", []), queue_path
        )

    return recovered, queue_changed


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        raise SystemExit(
            "Usage: python s1_price_range_history.py <s1_watch.json> <filings.json>"
        )
    recovered, queue_changed = repair_files(argv[0], argv[1])
    print(
        f"Recovered {recovered} authoritative pre-pricing range(s); "
        f"synchronized {queue_changed} researcher-queue row(s)"
    )


if __name__ == "__main__":
    main()

"""Validate the public Research Monitor feed against its versioned JSON Schema."""
from __future__ import annotations

import argparse
import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator
from price_lookup import MAX_FUTURE_SKEW_SECONDS, MAX_QUOTE_AGE_SECONDS

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
CIK_PATTERN = re.compile(r"^\d{10}$")
ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SEC_ARCHIVES_FILING_PATTERN = re.compile(
    r"^https://www\.sec\.gov/Archives/edgar/data/(\d+)/(\d{18})/[^/?#]+$",
    re.IGNORECASE,
)


def schema_path_for_version(version: int) -> Path:
    return SCHEMA_DIR / f"filings-v{version}.schema.json"


def load_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema(version: int) -> dict:
    path = schema_path_for_version(version)
    if not path.exists():
        raise ValueError(
            f"No public-feed schema is registered for schema_version={version}. "
            "Add a new versioned schema before publishing a breaking feed change."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _has_preliminary_price(filing: dict) -> bool:
    """Return True only when one of the public Filing Price aliases has a value."""
    for field in ("filing_price", "price_range"):
        value = filing.get(field)
        if value is not None and str(value).strip():
            return True
    return False


def _canonical_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def _aware_datetime(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _positive_number(value):
    """Return a finite positive numeric value, otherwise None."""
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def _normalize_cik(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else None


def _sec_identity_errors(index: int, filing: dict) -> list[str]:
    """Require canonical same-issuer SEC identity on every public filing row."""
    prefix = f"$.filings[{index}]"
    failures = []

    cik = str(filing.get("cik") or "").strip()
    accession = str(filing.get("accession_no") or "").strip()
    sec_url = str(filing.get("sec_url") or "").strip()

    row_cik = int(cik) if CIK_PATTERN.fullmatch(cik) else None
    if row_cik is None:
        failures.append(
            f"{prefix}.cik: public row must use a canonical 10-digit issuer CIK"
        )

    canonical_accession = (
        accession.replace("-", "")
        if ACCESSION_PATTERN.fullmatch(accession)
        else ""
    )
    if not canonical_accession:
        failures.append(
            f"{prefix}.accession_no: public row must use a canonical SEC accession number"
        )

    sec_url_match = SEC_ARCHIVES_FILING_PATTERN.fullmatch(sec_url)
    if sec_url_match is None:
        failures.append(
            f"{prefix}.sec_url: public row must use a canonical SEC Archives filing URL without query or fragment data"
        )
        return failures

    sec_url_cik = int(sec_url_match.group(1))
    sec_url_accession = sec_url_match.group(2)
    if row_cik is not None and sec_url_cik != row_cik:
        failures.append(
            f"{prefix}.sec_url: SEC URL issuer CIK does not match row CIK"
        )
    if canonical_accession and sec_url_accession != canonical_accession:
        failures.append(
            f"{prefix}.sec_url: SEC URL accession directory does not match row accession"
        )

    return failures


def _is_priced_424b4(filing: dict) -> bool:
    return (
        str(filing.get("form") or "").strip().upper() == "424B4"
        and str(filing.get("stage") or "").strip().casefold() == "priced"
    )


def _lifecycle_semantic_errors(
    index: int,
    filing: dict,
    generated_at=None,
) -> list[str]:
    """Reject impossible lifecycle/market states at the shared release boundary.

    All public-feed writers invoke this schema contract before publication. Keep the
    most important lifecycle invariants here as defense in depth so an upstream
    sanitizer or workflow-ordering regression cannot publish a pre-pricing quote,
    a stale quote, an unresolved final price, or impossible IPO chronology.
    """
    prefix = f"$.filings[{index}]"
    failures = []
    form = str(filing.get("form") or "").strip().upper()
    stage = str(filing.get("stage") or "").strip().casefold()
    final_form = form == "424B4"
    priced_stage = stage == "priced"
    priced_final = final_form and priced_stage

    if final_form != priced_stage:
        failures.append(
            f"{prefix}: final lifecycle state must pair form 424B4 with stage Priced"
        )

    filed_date = _canonical_date(filing.get("filed"))
    if filed_date is None:
        failures.append(
            f"{prefix}.filed: SEC filing date must be a canonical calendar date"
        )
    elif filed_date > date.today():
        failures.append(
            f"{prefix}.filed: SEC filing date cannot be in the future"
        )

    current_price = filing.get("current_price")
    price_updated = filing.get("price_updated")
    if current_price not in (None, ""):
        if not priced_final:
            failures.append(
                f"{prefix}.current_price: Current Price is permitted only for a 424B4/Priced lifecycle state"
            )
        elif _positive_number(current_price) is None:
            failures.append(
                f"{prefix}.current_price: Current Price must be a positive finite number when populated"
            )
        else:
            quote_time = _aware_datetime(price_updated)
            if quote_time is None:
                failures.append(
                    f"{prefix}.price_updated: Current Price requires a timezone-aware provider timestamp"
                )
            else:
                quote_utc = quote_time.astimezone(timezone.utc)
                quote_date = quote_utc.date()
                if quote_utc > datetime.now(timezone.utc):
                    failures.append(
                        f"{prefix}.price_updated: Current Price provider timestamp cannot be in the future"
                    )

                feed_generated_at = _aware_datetime(generated_at)
                if feed_generated_at is not None:
                    quote_age_seconds = (
                        feed_generated_at.astimezone(timezone.utc) - quote_utc
                    ).total_seconds()
                    if quote_age_seconds > MAX_QUOTE_AGE_SECONDS:
                        failures.append(
                            f"{prefix}.price_updated: Current Price provider timestamp is too old for the feed generation time"
                        )
                    elif quote_age_seconds < -MAX_FUTURE_SKEW_SECONDS:
                        failures.append(
                            f"{prefix}.price_updated: Current Price provider timestamp is too far after the feed generation time"
                        )

                pricing_date = _canonical_date(filing.get("pricing_date"))
                if pricing_date is not None and quote_date < pricing_date:
                    failures.append(
                        f"{prefix}.price_updated: Current Price provider timestamp cannot predate Pricing Date"
                    )
                if filed_date is not None and quote_date < filed_date:
                    failures.append(
                        f"{prefix}.price_updated: Current Price provider timestamp cannot predate the final 424B4 filing date"
                    )
    elif price_updated not in (None, ""):
        failures.append(
            f"{prefix}.price_updated: provider timestamp cannot remain populated without Current Price"
        )

    if priced_final:
        if _positive_number(filing.get("offering_price")) is None:
            failures.append(
                f"{prefix}.offering_price: priced 424B4 must have a positive Final IPO Price"
            )

        pricing_date = _canonical_date(filing.get("pricing_date"))
        if pricing_date is None:
            failures.append(
                f"{prefix}.pricing_date: priced 424B4 must have a canonical Pricing Date"
            )
        elif pricing_date > date.today():
            failures.append(
                f"{prefix}.pricing_date: priced 424B4 Pricing Date cannot be in the future"
            )
        elif filed_date is not None and pricing_date > filed_date:
            failures.append(
                f"{prefix}.pricing_date: Pricing Date cannot postdate the final 424B4 filing date"
            )

        filing_date_raw = filing.get("filing_date")
        filing_date = _canonical_date(filing_date_raw)
        if filing_date_raw not in (None, "") and filing_date is None:
            failures.append(
                f"{prefix}.filing_date: initial filing date must be canonical when populated"
            )
        elif filing_date is not None and pricing_date is not None and filing_date > pricing_date:
            failures.append(
                f"{prefix}.filing_date: initial filing date cannot postdate Pricing Date"
            )

    return failures


def _priced_filing_price_provenance_errors(index: int, filing: dict) -> list[str]:
    """Validate the authoritative SEC lineage behind a priced Filing Price.

    Lifecycle reconciliation can preserve a preliminary price while later export or
    merge steps accidentally drop or stale its source metadata. A priced 424B4 must
    therefore carry same-issuer, same-accession S-1/S-1A provenance for every
    nonblank Filing Price. Fail closed rather than allowing an untraceable value to
    outrank the authoritative history in the researcher UI.
    """
    if not _is_priced_424b4(filing) or not _has_preliminary_price(filing):
        return []

    prefix = f"$.filings[{index}].filing_price_source"
    failures = []

    filing_price = filing.get("filing_price")
    price_range = filing.get("price_range")
    filing_price_text = str(filing_price).strip() if filing_price not in (None, "") else ""
    price_range_text = str(price_range).strip() if price_range not in (None, "") else ""
    if filing_price_text and price_range_text and filing_price_text != price_range_text:
        failures.append(
            f"$.filings[{index}]: filing_price and price_range disagree for a priced IPO"
        )

    source = filing.get("filing_price_source")
    if not isinstance(source, dict):
        failures.append(f"{prefix}: populated Filing Price lacks SEC S-1/S-1A provenance")
        return failures

    if str(source.get("source") or "").strip().casefold() != "sec edgar":
        failures.append(f"{prefix}.source: Filing Price source must be SEC EDGAR")
    if str(source.get("form") or "").strip().upper() not in {"S-1", "S-1/A"}:
        failures.append(f"{prefix}.form: Filing Price source must be S-1 or S-1/A")

    accession = str(source.get("accession_no") or "").strip()
    if not ACCESSION_PATTERN.fullmatch(accession):
        failures.append(f"{prefix}.accession_no: Filing Price source must use a canonical SEC accession number")

    source_date = _canonical_date(source.get("filing_date"))
    if source_date is None:
        failures.append(f"{prefix}.filing_date: Filing Price source must use a canonical SEC filing date")

    pricing_date = _canonical_date(filing.get("pricing_date"))
    if pricing_date is None:
        failures.append(
            f"$.filings[{index}].pricing_date: priced IPO must have a canonical Pricing Date for Filing Price chronology"
        )
    elif source_date is not None and source_date > pricing_date:
        failures.append(f"{prefix}.filing_date: Filing Price source cannot postdate Pricing Date")

    sec_url = str(source.get("sec_url") or "").strip()
    row_cik = _normalize_cik(filing.get("cik"))
    sec_url_match = SEC_ARCHIVES_FILING_PATTERN.fullmatch(sec_url)
    sec_url_cik = int(sec_url_match.group(1)) if sec_url_match else None
    sec_url_accession = sec_url_match.group(2) if sec_url_match else ""

    if sec_url_match is None:
        failures.append(
            f"{prefix}.sec_url: Filing Price source must use a canonical SEC Archives filing URL without query or fragment data"
        )
    else:
        if row_cik is None:
            failures.append(f"$.filings[{index}].cik: priced IPO lacks a valid issuer CIK for Filing Price provenance")
        elif sec_url_cik != row_cik:
            failures.append(f"{prefix}.sec_url: Filing Price SEC URL issuer CIK does not match row CIK")

        if accession and ACCESSION_PATTERN.fullmatch(accession):
            if sec_url_accession != accession.replace("-", ""):
                failures.append(f"{prefix}.sec_url: Filing Price SEC URL does not match source accession")

    return failures


def _ownership_provenance_errors(index: int, filing: dict) -> list[str]:
    """Validate an optional SEC owner snapshot without requiring legacy backfill."""
    source = filing.get("ownership_source")
    if source is None:
        return []

    prefix = f"$.filings[{index}].ownership_source"
    failures = []
    if not filing.get("people"):
        failures.append(f"{prefix}: ownership provenance cannot exist without named owners")
    if not isinstance(source, dict):
        return failures

    if str(source.get("source") or "").strip().casefold() != "sec edgar":
        failures.append(f"{prefix}.source: ownership source must be SEC EDGAR")
    if str(source.get("form") or "").strip().upper() not in {"S-1", "S-1/A", "424B4"}:
        failures.append(f"{prefix}.form: ownership source must be S-1, S-1/A, or 424B4")

    accession = str(source.get("accession_no") or "").strip()
    canonical_accession = accession.replace("-", "") if ACCESSION_PATTERN.fullmatch(accession) else ""
    if not canonical_accession:
        failures.append(f"{prefix}.accession_no: ownership source must use a canonical SEC accession number")

    source_date = _canonical_date(source.get("filing_date"))
    if source_date is None:
        failures.append(f"{prefix}.filing_date: ownership source must use a canonical SEC filing date")
    row_date = _canonical_date(filing.get("filed"))
    if source_date is not None and row_date is not None and source_date > row_date:
        failures.append(f"{prefix}.filing_date: ownership source cannot postdate the public filing row")

    sec_url = str(source.get("sec_url") or "").strip()
    sec_url_match = SEC_ARCHIVES_FILING_PATTERN.fullmatch(sec_url)
    if sec_url_match is None:
        failures.append(
            f"{prefix}.sec_url: ownership source must use a canonical SEC Archives filing URL without query or fragment data"
        )
        return failures

    row_cik = _normalize_cik(filing.get("cik"))
    if row_cik is not None and int(sec_url_match.group(1)) != row_cik:
        failures.append(f"{prefix}.sec_url: ownership SEC URL issuer CIK does not match row CIK")
    if canonical_accession and sec_url_match.group(2) != canonical_accession:
        failures.append(f"{prefix}.sec_url: ownership SEC URL does not match source accession")
    return failures


def _semantic_errors(payload: dict) -> list[str]:
    """Enforce cross-field provenance rules that JSON Schema alone cannot express."""
    failures = []
    filings = payload.get("filings")
    if not isinstance(filings, list):
        return failures

    generated_at = payload.get("generated_at")
    for index, filing in enumerate(filings):
        if not isinstance(filing, dict):
            continue
        if filing.get("filing_price_source") is not None and not _has_preliminary_price(filing):
            failures.append(
                f"$.filings[{index}].filing_price_source: SEC Filing Price provenance "
                "cannot remain populated when both filing_price and price_range are blank"
            )
        failures.extend(_sec_identity_errors(index, filing))
        failures.extend(_lifecycle_semantic_errors(index, filing, generated_at))
        failures.extend(_priced_filing_price_provenance_errors(index, filing))
        failures.extend(_ownership_provenance_errors(index, filing))
    return failures


def validate_payload(payload: dict) -> list[str]:
    version = payload.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        return ["schema_version must be an integer"]
    try:
        schema = load_schema(version)
    except ValueError as exc:
        return [str(exc)]

    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        location = "$"
        for part in error.absolute_path:
            location += f"[{part}]" if isinstance(part, int) else f".{part}"
        errors.append(f"{location}: {error.message}")
    errors.extend(_semantic_errors(payload))
    return errors


def validate_file(path: str | Path) -> list[str]:
    path = Path(path)
    try:
        payload = load_payload(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Unable to read feed JSON: {exc}"]
    return validate_payload(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "feed",
        nargs="?",
        default=str(ROOT / "docs" / "data" / "filings.json"),
        help="Path to the public filings JSON feed",
    )
    args = parser.parse_args()

    failures = validate_file(args.feed)
    if failures:
        raise SystemExit("Public feed schema validation failed:\n- " + "\n- ".join(failures))

    payload = load_payload(Path(args.feed))
    print(
        f"Public feed schema v{payload['schema_version']} valid: "
        f"{len(payload.get('filings', []))} filing(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

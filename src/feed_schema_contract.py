"""Validate the public Research Monitor feed against its versioned JSON Schema."""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
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


def _normalize_cik(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else None


def _is_priced_424b4(filing: dict) -> bool:
    return (
        str(filing.get("form") or "").strip().upper() == "424B4"
        and str(filing.get("stage") or "").strip().casefold() == "priced"
    )


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


def _semantic_errors(payload: dict) -> list[str]:
    """Enforce cross-field provenance rules that JSON Schema alone cannot express."""
    failures = []
    filings = payload.get("filings")
    if not isinstance(filings, list):
        return failures

    for index, filing in enumerate(filings):
        if not isinstance(filing, dict):
            continue
        if filing.get("filing_price_source") is not None and not _has_preliminary_price(filing):
            failures.append(
                f"$.filings[{index}].filing_price_source: SEC Filing Price provenance "
                "cannot remain populated when both filing_price and price_range are blank"
            )
        failures.extend(_priced_filing_price_provenance_errors(index, filing))
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

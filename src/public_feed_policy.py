"""Release policy gate for the public Research Monitor feed."""

from __future__ import annotations

import json
import math
from pathlib import Path

from dashboard_export import write_dashboard_csv
from edgar_client import INVESTMENT_PRODUCT_NAME_PATTERN, SPAC_NAME_PATTERN

MINIMUM_IPO_VALUE = 100_000_000.0


def _number(value):
    """Parse only explicit numeric values; never infer or estimate a missing size."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _has_excluded_issuer_name(filing):
    """Fail closed for issuer names that independently identify excluded products.

    Full SPAC/reverse-SPAC/investment-product detection remains upstream because it
    can inspect filing text. This release gate adds a final deterministic safeguard
    for name patterns that are strong enough to classify without inference.
    """
    company = str((filing or {}).get("company") or "").strip()
    return bool(
        SPAC_NAME_PATTERN.search(company)
        or INVESTMENT_PRODUCT_NAME_PATTERN.search(company)
    )


def _has_safe_s1_size_provenance(filing):
    """Reject S-1 sizes that can be resale/reference-price arithmetic in disguise.

    A preliminary range is inherently offering-specific. For fixed-price S-1 rows,
    require explicit issuer-offering provenance before the release gate will trust
    the numeric value. Selling-stockholder/resale language always wins over generic
    cover-page wording. This deliberately fails closed: a real IPO may be
    temporarily omitted, but a resale registration must never be promoted as a
    qualifying IPO.
    """
    form = str((filing or {}).get("form") or "").strip().upper()
    if form not in {"S-1", "S-1/A"}:
        return True

    price_range = str((filing or {}).get("price_range") or "").strip()
    if price_range:
        return True

    source = str((filing or {}).get("offering_size_source") or "").strip().lower()
    confidence = str((filing or {}).get("offering_size_confidence") or "").strip().lower()

    resale_markers = (
        "selling stockholder",
        "selling shareholder",
        "selling securityholder",
        "resale",
        "secondary-only",
        "secondary only",
    )
    if any(marker in source for marker in resale_markers):
        return False

    issuer_markers = (
        "issuer-only",
        "issuer only",
        "issuer offering",
        "company offering",
        "primary offering",
    )
    return confidence == "high" and any(marker in source for marker in issuer_markers)


def qualifies_for_public_feed(filing):
    """Return True only for qualifying operating-company IPOs established at >= $100M."""
    if not isinstance(filing, dict):
        return False
    if _has_excluded_issuer_name(filing):
        return False
    if not _has_safe_s1_size_provenance(filing):
        return False
    value = _number(filing.get("value"))
    return value is not None and value >= MINIMUM_IPO_VALUE


def enforce_public_feed_policy(output_path):
    """Remove non-qualifying records and keep the CSV companion in sync."""
    output_path = Path(output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("Public feed must contain a filings list")

    qualifying = [filing for filing in filings if qualifies_for_public_feed(filing)]
    removed = len(filings) - len(qualifying)
    if removed:
        payload["filings"] = qualifying
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)
    write_dashboard_csv(payload.get("filings", []), output_path)
    return payload, removed


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../docs/data/filings.json")
    _, removed_count = enforce_public_feed_policy(target)
    print(f"Public-feed policy removed {removed_count} non-qualifying filing(s)")

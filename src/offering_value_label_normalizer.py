"""Normalize Research Monitor writer output without changing authoritative offering values.

The Daily pipeline already canonicalizes ``value_label`` while reconciling final
424B4 offering values. The S-1 writer does not run that SEC reconciliation step,
so it can otherwise publish a different label for the same unchanged raw
``value``. Keep writer output convergent by applying the dashboard's existing
money formatter only to the derived display label. No offering value is inferred,
replaced, rounded, or used as an eligibility gate here.

The S-1 writer also reaches this normalizer before its final quote-identity review.
Run the shared public sanitizer after label normalization so regenerated holder
dollar arithmetic cannot bypass the cents-normalization and fail-closed quote
contract already used by the other public-feed writers.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import dashboard_export
import prepricing_quote_sanitizer


def normalize_payload(payload: dict) -> tuple[dict, int]:
    """Synchronize derived ``value_label`` fields with explicit raw offering values."""
    if not isinstance(payload, dict):
        raise ValueError("Offering-value label normalization requires an object payload")

    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("Public feed must contain a filings list")

    changed = 0
    for filing in filings:
        if not isinstance(filing, dict):
            continue
        expected = dashboard_export._money(filing.get("value"))
        if filing.get("value_label") == expected:
            continue
        filing["value_label"] = expected
        changed += 1
    return payload, changed


def normalize_file(path: str | Path) -> int:
    """Normalize one feed atomically and enforce shared public-release sanitation."""
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload, changed = normalize_payload(payload)
    if changed:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    # Preserve the label normalizer's return contract while ensuring the S-1 writer
    # cannot reintroduce floating-point tails or unsafe quote-derived holder values.
    # The shared sanitizer also keeps the flattened CSV synchronized when it changes
    # the public JSON feed.
    prepricing_quote_sanitizer.sanitize_file(path)
    return changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize derived IPO offering-value labels without changing raw values."
    )
    parser.add_argument("feed", help="Path to docs/data/filings.json")
    args = parser.parse_args(argv)
    changed = normalize_file(args.feed)
    print(f"Normalized offering-value display labels for {changed} filing(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

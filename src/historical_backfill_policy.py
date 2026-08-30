"""Historical publication threshold for month-specific Research Monitor backfills."""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path

from dashboard_export import write_dashboard_csv

DEFAULT_HISTORICAL_MINIMUM = 100_000_000.0


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _iso_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def apply_historical_minimum(
    output_path,
    *,
    start: date,
    end: date,
    minimum_value: float = DEFAULT_HISTORICAL_MINIMUM,
):
    """Apply the pre-any-size publication threshold only to the replayed month.

    The canonical ``filed`` date determines month membership. Rows outside the
    requested historical replay window are left untouched, including any valid
    go-forward sub-$100M IPOs already present in the feed.
    """
    if start > end:
        raise ValueError("Historical backfill start must not be after end")
    if minimum_value <= 0 or not math.isfinite(float(minimum_value)):
        raise ValueError("Historical backfill minimum must be a positive finite number")

    output_path = Path(output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("Public feed must contain a filings list")

    kept = []
    removed = []
    for filing in filings:
        if not isinstance(filing, dict):
            kept.append(filing)
            continue
        filed = _iso_date(filing.get("filed"))
        if filed is not None and start <= filed <= end:
            value = _number(filing.get("value"))
            if value is None or value < minimum_value:
                removed.append(
                    str(filing.get("company") or filing.get("accession_number") or "unknown")
                )
                continue
        kept.append(filing)

    payload["filings"] = kept
    if kept != filings:
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)

    write_dashboard_csv(kept, output_path)
    return payload, removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_path")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument(
        "--minimum-value",
        type=float,
        default=DEFAULT_HISTORICAL_MINIMUM,
    )
    args = parser.parse_args()

    start = _iso_date(args.start)
    end = _iso_date(args.end)
    if start is None or end is None:
        raise SystemExit("Historical backfill start/end must be ISO dates")

    _, removed = apply_historical_minimum(
        args.output_path,
        start=start,
        end=end,
        minimum_value=args.minimum_value,
    )
    print(
        f"Historical backfill policy removed {len(removed)} filing(s) "
        f"below ${args.minimum_value:,.0f} or with unknown size in "
        f"{args.start}..{args.end}"
    )


if __name__ == "__main__":
    main()
